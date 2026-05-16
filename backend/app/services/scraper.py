import asyncio
import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.models import Company, Job, ATSPlatform
from app.services.ats_parser import (
    BaseATSParser,
    GreenhouseParser,
    LeverParser,
    WorkdayParser,
    ICIMSParser,
    AshbyParser,
    CustomParser,
)
from app.services.llm_extractor import extract_jobs_from_page

import httpx

logger = logging.getLogger(__name__)

ATS_PARSERS: dict[ATSPlatform, BaseATSParser] = {
    ATSPlatform.GREENHOUSE: GreenhouseParser(),
    ATSPlatform.LEVER: LeverParser(),
    ATSPlatform.WORKDAY: WorkdayParser(),
    ATSPlatform.ICIMS: ICIMSParser(),
    ATSPlatform.ASHBY: AshbyParser(),
    ATSPlatform.CUSTOM: CustomParser(),
}

CONCURRENCY_LIMIT = 5
REQUEST_TIMEOUT = 30.0


async def scrape_company(company: Company, client: httpx.AsyncClient) -> list[dict]:
    parser = ATS_PARSERS.get(company.ats_platform, CustomParser())
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


async def upsert_jobs(jobs_data: list[dict], session: AsyncSession) -> int:
    upserted = 0
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
        existing_job = existing.scalar_one_or_none()

        if existing_job:
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
        existing_by_url_job = existing_by_url.scalar_one_or_none()

        if existing_by_url_job:
            if content_hash and existing_by_url_job.content_hash != content_hash:
                existing_by_url_job.content_hash = content_hash
                if job_data.get("description"):
                    existing_by_url_job.description = job_data["description"]
                if job_data.get("title"):
                    existing_by_url_job.title = job_data["title"]
                existing_by_url_job.updated_at = datetime.now(timezone.utc)
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
            url=job_data.get("url", ""),
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
            jobs = await scrape_company(company, client)
            total_jobs += len(jobs)

            async with async_session() as session:
                new_count = await upsert_jobs(jobs, session)
                total_new += new_count

            async with async_session() as session:
                company_obj = await session.get(Company, company.id)
                if company_obj:
                    company_obj.last_scraped_at = datetime.now(timezone.utc)
                    company_obj.scrape_status = "success"
                    await session.commit()

    headers = {
        "User-Agent": "VJob/0.1.0 (AI Job Intelligence Agent; +https://github.com/vasubhrdwj/JobFetcher)",
        "Accept": "text/html,application/json",
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=headers, follow_redirects=True) as client:
        tasks = [scrape_with_semaphore(company, client) for company in companies]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to scrape {companies[i].name}: {result}")
                async with async_session() as session:
                    company_obj = await session.get(Company, companies[i].id)
                    if company_obj:
                        company_obj.scrape_status = f"error: {str(result)[:200]}"
                        company_obj.last_scraped_at = datetime.now(timezone.utc)
                        await session.commit()

    logger.info(f"Scrape complete: {total_jobs} total jobs, {total_new} new jobs inserted")
    return {"total_jobs": total_jobs, "new_jobs": total_new, "companies_scraped": len(companies)}


async def scrape_single_company(company_id: int) -> dict:
    async with async_session() as session:
        company = await session.get(Company, company_id)
        if not company:
            return {"error": f"Company {company_id} not found"}

    headers = {
        "User-Agent": "VJob/0.1.0 (AI Job Intelligence Agent; +https://github.com/vasubhrdwj/JobFetcher)",
        "Accept": "text/html,application/json",
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=headers, follow_redirects=True) as client:
        jobs = await scrape_company(company, client)

    async with async_session() as session:
        new_count = await upsert_jobs(jobs, session)

    async with async_session() as session:
        company_obj = await session.get(Company, company_id)
        if company_obj:
            company_obj.last_scraped_at = datetime.now(timezone.utc)
            company_obj.scrape_status = "success"
            await session.commit()

    return {"company": company.name, "total_jobs": len(jobs), "new_jobs": new_count}