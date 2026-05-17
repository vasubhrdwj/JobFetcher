import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, and_

from app.database import async_session
from app.models.models import Company, Job
from app.services.ats_parser import ATS_PARSERS

logger = logging.getLogger(__name__)

CONCURRENCY_LIMIT = 5
REQUEST_TIMEOUT = 30.0
HEADERS = {
    "User-Agent": "VJob/0.2.0 (AI Job Intelligence; +https://github.com/vasubhrdwj/JobFetcher)",
    "Accept": "text/html,application/json",
}


async def scrape_company(company: Company, client: httpx.AsyncClient) -> list[dict]:
    ats_key = company.ats_platform.value if hasattr(company.ats_platform, "value") else str(company.ats_platform)
    parser = ATS_PARSERS.get(ats_key, ATS_PARSERS["custom"])
    try:
        logger.info(f"Scraping {company.name} ({company.ats_platform}) - {company.career_url}")
        jobs = await parser.parse_jobs(company, client)
        for job in jobs:
            job["company_id"] = company.id
        logger.info(f"Found {len(jobs)} jobs for {company.name}")
        return jobs
    except Exception as e:
        logger.error(f"Error scraping {company.name}: {e}")
        return []


async def upsert_jobs(jobs_data: list[dict]) -> int:
    if not jobs_data:
        return 0
    upserted = 0
    async with async_session() as session:
        for job_data in jobs_data:
            company_id = job_data.get("company_id")
            content_hash = job_data.get("content_hash")

            existing = await session.execute(
                select(Job).where(
                    and_(
                        Job.company_id == company_id,
                        Job.content_hash == content_hash,
                        Job.is_active == True,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue

            url = job_data.get("url", "")
            existing_by_url = await session.execute(
                select(Job).where(
                    and_(
                        Job.company_id == company_id,
                        Job.url == url,
                        Job.is_active == True,
                    )
                )
            )
            existing_job = existing_by_url.scalar_one_or_none()

            if existing_job:
                if content_hash and existing_job.content_hash != content_hash:
                    existing_job.content_hash = content_hash
                    if job_data.get("description"):
                        existing_job.description = job_data["description"]
                    if job_data.get("title"):
                        existing_job.title = job_data["title"]
                continue

            posted_at = job_data.get("posted_at")
            if isinstance(posted_at, str):
                try:
                    posted_at = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    posted_at = None
            elif not isinstance(posted_at, datetime):
                posted_at = None

            job = Job(
                company_id=company_id,
                title=job_data.get("title", "Unknown Title"),
                url=url,
                location=job_data.get("location"),
                job_type=job_data.get("job_type"),
                seniority=job_data.get("seniority"),
                description=job_data.get("description"),
                requirements=job_data.get("requirements"),
                responsibilities=job_data.get("responsibilities"),
                is_remote=job_data.get("is_remote"),
                salary_min=job_data.get("salary_min"),
                salary_max=job_data.get("salary_max"),
                source=job_data.get("source", "ats_direct"),
                content_hash=content_hash,
                posted_at=posted_at,
            )
            session.add(job)
            upserted += 1

        await session.commit()
    return upserted


async def _update_company_status(company_id: int, status: str):
    async with async_session() as session:
        company_obj = await session.get(Company, company_id)
        if company_obj:
            company_obj.last_scraped_at = datetime.now(timezone.utc)
            company_obj.scrape_status = status
            await session.commit()


async def scrape_all_companies():
    async with async_session() as session:
        result = await session.execute(
            select(Company).where(Company.is_active == True).order_by(Company.name)
        )
        companies = result.scalars().all()

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    total_jobs = 0
    total_new = 0

    async def scrape_with_semaphore(company: Company, client: httpx.AsyncClient):
        nonlocal total_jobs, total_new
        async with semaphore:
            try:
                jobs = await scrape_company(company, client)
                total_jobs += len(jobs)
                new_count = await upsert_jobs(jobs)
                total_new += new_count
                await _update_company_status(company.id, "success")
            except Exception as e:
                logger.error(f"Failed to scrape {company.name}: {e}")
                await _update_company_status(company.id, f"error: {str(e)[:200]}")

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        tasks = [scrape_with_semaphore(company, client) for company in companies]
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info(f"Scrape complete: {total_jobs} total jobs, {total_new} new jobs inserted")
    return {"total_jobs": total_jobs, "new_jobs": total_new, "companies_scraped": len(companies)}


async def scrape_single_company(company_id: int) -> dict:
    async with async_session() as session:
        company = await session.get(Company, company_id)
        if not company:
            return {"error": f"Company {company_id} not found"}

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        jobs = await scrape_company(company, client)

    new_count = await upsert_jobs(jobs)
    await _update_company_status(company_id, "success")

    return {"company": company.name, "total_jobs": len(jobs), "new_jobs": new_count}