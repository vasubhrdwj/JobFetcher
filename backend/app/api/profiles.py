from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import UserProfile
from app.schemas.user import UserProfileCreate, UserProfileOut

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/", response_model=list[UserProfileOut])
async def list_profiles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserProfile).order_by(UserProfile.created_at.desc()))
    return result.scalars().all()


@router.get("/{profile_id}", response_model=UserProfileOut)
async def get_profile(profile_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserProfile).where(UserProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.post("/", response_model=UserProfileOut, status_code=201)
async def create_profile(data: UserProfileCreate, db: AsyncSession = Depends(get_db)):
    dump = data.model_dump()
    if dump.get("target_companies") and isinstance(dump["target_companies"], list):
        dump["target_companies"] = dump["target_companies"]
    if dump.get("target_locations") and isinstance(dump["target_locations"], list):
        dump["target_locations"] = dump["target_locations"]
    if dump.get("skills") and isinstance(dump["skills"], list):
        dump["skills"] = dump["skills"]
    profile = UserProfile(**dump)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.put("/{profile_id}", response_model=UserProfileOut)
async def update_profile(
    profile_id: int, data: UserProfileCreate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(UserProfile).where(UserProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.post("/{profile_id}/resume", response_model=UserProfileOut)
async def upload_resume(
    profile_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(UserProfile).where(UserProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    content = await file.read()

    if file.filename and file.filename.lower().endswith(b".pdf"):
        from PyPDF2 import PdfReader
        import io
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        text = content.decode("utf-8", errors="replace")

    profile.resume_text = text
    await db.commit()
    await db.refresh(profile)
    return profile