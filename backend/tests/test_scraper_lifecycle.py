import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.database import async_session, engine
from app.models.models import Base, Company, Job, ATSPlatform
from app.services.scraper import _sweep_stale_jobs


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_stale_sweep_deactivates_missing_jobs():
    now = datetime.now(timezone.utc)
    earlier = now - timedelta(hours=2)

    async with async_session() as session:
        company = Company(
            name="TestCorp_Sweep",
            career_url="https://testcorpsweep.com/careers",
            ats_platform=ATSPlatform.CUSTOM,
            is_active=True,
        )
        session.add(company)
        await session.commit()
        await session.refresh(company)
        cid = company.id

    async with async_session() as session:
        job_a = Job(
            company_id=cid,
            title="Engineer A",
            url="https://testcorpsweep.com/jobs/a",
            content_hash="hash_a_sweep",
            is_active=True,
            last_seen_at=now,
            source="custom",
        )
        job_b = Job(
            company_id=cid,
            title="Engineer B",
            url="https://testcorpsweep.com/jobs/b",
            content_hash="hash_b_sweep",
            is_active=True,
            last_seen_at=earlier,
            source="custom",
        )
        session.add_all([job_a, job_b])
        await session.commit()

    run_started = now - timedelta(minutes=30)
    await _sweep_stale_jobs({cid}, run_started)

    async with async_session() as session:
        result = await session.execute(select(Job).where(Job.company_id == cid))
        jobs = result.scalars().all()

        job_a_db = [j for j in jobs if j.title == "Engineer A"][0]
        job_b_db = [j for j in jobs if j.title == "Engineer B"][0]

        assert job_a_db.is_active is True
        assert job_b_db.is_active is False


@pytest.mark.asyncio
async def test_empty_scrape_does_not_sweep():
    earlier = datetime.now(timezone.utc) - timedelta(hours=2)

    async with async_session() as session:
        company = Company(
            name="TestCorp_Empty",
            career_url="https://testcorpempty.com/careers",
            ats_platform=ATSPlatform.CUSTOM,
            is_active=True,
        )
        session.add(company)
        await session.commit()
        await session.refresh(company)
        cid = company.id

    async with async_session() as session:
        job = Job(
            company_id=cid,
            title="Engineer A Empty",
            url="https://testcorpempty.com/jobs/a",
            content_hash="hash_a_empty",
            is_active=True,
            last_seen_at=earlier,
            source="custom",
        )
        session.add(job)
        await session.commit()

    await _sweep_stale_jobs(set(), datetime.now(timezone.utc))

    async with async_session() as session:
        result = await session.execute(select(Job).where(Job.company_id == cid))
        jobs = result.scalars().all()

        assert len(jobs) == 1
        assert jobs[0].is_active is True