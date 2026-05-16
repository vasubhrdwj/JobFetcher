from fastapi import APIRouter

from app.api.companies import router as companies_router
from app.api.jobs import router as jobs_router
from app.api.profiles import router as profiles_router
from app.api.applications import router as applications_router

router = APIRouter()
router.include_router(companies_router)
router.include_router(jobs_router)
router.include_router(profiles_router)
router.include_router(applications_router)