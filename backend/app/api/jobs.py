from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import Job, Company
from app.schemas.job import JobCreate, JobOut, JobList

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", response_model=JobList)
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    company_id: int | None = None,
    is_remote: bool | None = None,
    is_active: bool | None = True,
    seniority: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Job).options(selectinload(Job.company))
    count_query = select(func.count()).select_from(Job)

    if company_id:
        query = query.where(Job.company_id == company_id)
        count_query = count_query.where(Job.company_id == company_id)
    if is_remote is not None:
        query = query.where(Job.is_remote == is_remote)
        count_query = count_query.where(Job.is_remote == is_remote)
    if is_active is not None:
        query = query.where(Job.is_active == is_active)
        count_query = count_query.where(Job.is_active == is_active)
    if seniority:
        query = query.where(Job.seniority == seniority)
        count_query = count_query.where(Job.seniority == seniority)
    if search:
        query = query.where(Job.title.ilike(f"%{search}%"))
        count_query = count_query.where(Job.title.ilike(f"%{search}%"))

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.offset(skip).limit(limit).order_by(Job.discovered_at.desc())
    )
    jobs = result.scalars().all()

    job_outs = []
    for j in jobs:
        jo = JobOut.model_validate(j)
        jo.company_name = j.company.name if j.company else None
        job_outs.append(jo)

    return JobList(jobs=job_outs, total=total)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Job).options(selectinload(Job.company)).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    jo = JobOut.model_validate(job)
    jo.company_name = job.company.name if job.company else None
    return jo


@router.post("/", response_model=JobOut, status_code=201)
async def create_job(data: JobCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.id == data.company_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Company not found")

    job = Job(**data.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return JobOut.model_validate(job)


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.delete(job)
    await db.commit()