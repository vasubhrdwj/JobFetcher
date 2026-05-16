from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Company, Job
from app.schemas.company import CompanyCreate, CompanyOut, CompanyList

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", response_model=CompanyList)
async def list_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ats_platform: str | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Company)
    count_query = select(func.count()).select_from(Company)

    if ats_platform:
        query = query.where(Company.ats_platform == ats_platform)
        count_query = count_query.where(Company.ats_platform == ats_platform)
    if is_active is not None:
        query = query.where(Company.is_active == is_active)
        count_query = count_query.where(Company.is_active == is_active)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(query.offset(skip).limit(limit).order_by(Company.name))
    companies = result.scalars().all()

    company_outs = []
    for c in companies:
        job_count = (await db.execute(
            select(func.count()).where(Job.company_id == c.id, Job.is_active == True)
        )).scalar() or 0
        co = CompanyOut.model_validate(c)
        co.job_count = job_count
        company_outs.append(co)

    return CompanyList(companies=company_outs, total=total)


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    job_count = (await db.execute(
        select(func.count()).where(Job.company_id == company.id, Job.is_active == True)
    )).scalar() or 0
    co = CompanyOut.model_validate(company)
    co.job_count = job_count
    return co


@router.post("/", response_model=CompanyOut, status_code=201)
async def create_company(data: CompanyCreate, db: AsyncSession = Depends(get_db)):
    company = Company(**data.model_dump())
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return CompanyOut.model_validate(company)


@router.put("/{company_id}", response_model=CompanyOut)
async def update_company(
    company_id: int, data: CompanyCreate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    for key, value in data.model_dump().items():
        setattr(company, key, value)
    await db.commit()
    await db.refresh(company)
    return CompanyOut.model_validate(company)


@router.delete("/{company_id}", status_code=204)
async def delete_company(company_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    await db.delete(company)
    await db.commit()