from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import Application, ApplicationStatus
from app.schemas.application import ApplicationCreate, ApplicationUpdate, ApplicationOut

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/", response_model=list[ApplicationOut])
async def list_applications(
    user_id: int | None = None,
    status: ApplicationStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Application).options(selectinload(Application.job))

    if user_id:
        query = query.where(Application.user_id == user_id)
    if status:
        query = query.where(Application.status == status)

    result = await db.execute(
        query.offset(skip).limit(limit).order_by(Application.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/{application_id}", response_model=ApplicationOut)
async def get_application(application_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.post("/", response_model=ApplicationOut, status_code=201)
async def create_application(data: ApplicationCreate, db: AsyncSession = Depends(get_db)):
    application = Application(**data.model_dump())
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return application


@router.patch("/{application_id}", response_model=ApplicationOut)
async def update_application(
    application_id: int, data: ApplicationUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    update_data = data.model_dump(exclude_unset=True)
    if data.status == ApplicationStatus.APPLIED and not application.applied_at:
        update_data["applied_at"] = datetime.now(timezone.utc)

    for key, value in update_data.items():
        setattr(application, key, value)
    await db.commit()
    await db.refresh(application)
    return application


@router.delete("/{application_id}", status_code=204)
async def delete_application(application_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    await db.delete(application)
    await db.commit()