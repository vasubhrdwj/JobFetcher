import pytest
from sqlalchemy import select

from app.database import async_session, engine
from app.models.models import Base, Company, Job, ATSPlatform
from app.services.scraper import upsert_jobs


@pytest.mark.asyncio
async def test_unique_constraint_prevents_duplicate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        company = Company(
            name="DedupCorp",
            career_url="https://dedupcorp.com/careers",
            ats_platform=ATSPlatform.CUSTOM,
            is_active=True,
        )
        session.add(company)
        await session.commit()
        await session.refresh(company)
        cid = company.id

    job_data = [{
        "company_id": cid,
        "title": "Senior Engineer",
        "url": "https://dedupcorp.com/jobs/123_dedup",
        "content_hash": "hash_original_dedup",
        "source": "custom",
    }]
    inserted = await upsert_jobs(job_data)
    assert inserted == 1

    job_data_updated = [{
        "company_id": cid,
        "title": "Senior Engineer Updated",
        "url": "https://dedupcorp.com/jobs/123_dedup",
        "content_hash": "hash_new_dedup",
        "source": "custom",
    }]
    inserted_again = await upsert_jobs(job_data_updated)
    assert inserted_again == 0

    async with async_session() as session:
        result = await session.execute(select(Job).where(Job.company_id == cid))
        jobs = result.scalars().all()
        assert len(jobs) == 1
        assert jobs[0].last_seen_at is not None
        assert jobs[0].title == "Senior Engineer Updated"
        assert jobs[0].content_hash == "hash_new_dedup"