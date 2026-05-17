import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, and_, update
from sqlalchemy.exc import IntegrityError

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
        raise


def _parse_posted_at(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            logger.debug(f"Could not parse posted_at: {value!r}")
            return None
    return None


async def upsert_jobs(jobs_data: list[dict]) -> int:
    if not jobs_data:
        return 0
    skipped_empty = 0
    upserted = 0
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        for job_data in jobs_data:
            company_id = job_data.get("company_id")
            url = job_data.get("url", "")
            if not url:
                skipped_empty += 1
                continue
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
                existing_job.last_seen_at = now
                if content_hash and existing_job.content_hash != content_hash:
                    existing_job.content_hash = content_hash
                    if job_data.get("description"):
                        existing_job.description = job_data["description"]
                    if job_data.get("title"):
                        existing_job.title = job_data["title"]
                continue

            existing_by_url = await session.execute(
                select(Job).where(
                    and_(
                        Job.company_id == company_id,
                        Job.url == url,
                        Job.is_active == True,
                    )
                )
            )
            existing_url_job = existing_by_url.scalar_one_or_none()

            if existing_url_job:
                existing_url_job.last_seen_at = now
                if content_hash and existing_url_job.content_hash != content_hash:
                    existing_url_job.content_hash = content_hash
                    if job_data.get("description"):
                        existing_url_job.description = job_data["description"]
                    if job_data.get("title"):
                        existing_url_job.title = job_data["title"]
                continue

            posted_at = _parse_posted_at(job_data.get("posted_at"))

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
                last_seen_at=now,
            )
            try:
                session.add(job)
                await session.flush()
                upserted += 1
            except IntegrityError:
                await session.rollback()
                continue

        if skipped_empty:
            logger.debug(f"Skipped {skipped_empty} jobs with empty URLs")
        await session.commit()
    return upserted


async def _update_company_status(company_id: int, status: str):
    async with async_session() as session:
        company_obj = await session.get(Company, company_id)
        if company_obj:
            company_obj.last_scraped_at = datetime.now(timezone.utc)
            company_obj.scrape_status = status[:250]
            await session.commit()


async def _sweep_stale_jobs(scraped_company_ids: set[int], run_started_at: datetime):
    async with async_session() as session:
        result = await session.execute(
            update(Job)
            .where(
                and_(
                    Job.is_active == True,
                    Job.company_id.in_(scraped_company_ids),
                    Job.last_seen_at < run_started_at,
                )
            )
            .values(is_active=False)
        )
        deactivated = result.rowcount
        await session.commit()
    if deactivated:
        logger.info(f"Deactivated {deactivated} stale jobs")


async def scrape_all_companies():
    run_started_at = datetime.now(timezone.utc)

    async with async_session() as session:
        result = await session.execute(
            select(Company).where(Company.is_active == True).order_by(Company.name)
        )
        companies = result.scalars().all()

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    results: list[tuple[int, int, int, str]] = []

    async def scrape_with_semaphore(company: Company, client: httpx.AsyncClient):
        async with semaphore:
            try:
                jobs = await scrape_company(company, client)
                new_count = await upsert_jobs(jobs)
                if len(jobs) > 0:
                    status = "success"
                else:
                    status = "success_empty"
                await _update_company_status(company.id, status)
                results.append((company.id, len(jobs), new_count, status))
            except httpx.HTTPError as e:
                status = f"http_error: {str(e)[:200]}"
                await _update_company_status(company.id, status)
                results.append((company.id, 0, 0, status))
            except Exception as e:
                status = f"parse_failed: {str(e)[:200]}"
                await _update_company_status(company.id, status)
                results.append((company.id, 0, 0, status))

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        tasks = [scrape_with_semaphore(company, client) for company in companies]
        await asyncio.gather(*tasks, return_exceptions=True)

    scraped_company_ids = {cid for cid, _, _, status in results if status == "success"}
    await _sweep_stale_jobs(scraped_company_ids, run_started_at)

    total_jobs = sum(jobs_count for _, jobs_count, _, _ in results)
    total_new = sum(new_count for _, _, new_count, _ in results)
    logger.info(f"Scrape complete: {total_jobs} total jobs, {total_new} new jobs inserted across {len(companies)} companies")
    return {"total_jobs": total_jobs, "new_jobs": total_new, "companies_scraped": len(companies)}


async def scrape_single_company(company_id: int) -> dict:
    async with async_session() as session:
        company = await session.get(Company, company_id)
        if not company:
            return {"error": f"Company {company_id} not found"}

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        try:
            jobs = await scrape_company(company, client)
        except httpx.HTTPError as e:
            status = f"http_error: {str(e)[:200]}"
            await _update_company_status(company_id, status)
            return {"error": status}
        except Exception as e:
            status = f"parse_failed: {str(e)[:200]}"
            await _update_company_status(company_id, status)
            return {"error": status}

    new_count = await upsert_jobs(jobs)
    if len(jobs) > 0:
        status = "success"
    else:
        status = "success_empty"
    await _update_company_status(company_id, status)

    return {"company": company.name, "total_jobs": len(jobs), "new_jobs": new_count}