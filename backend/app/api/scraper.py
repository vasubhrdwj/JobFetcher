from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Company
from app.services.scraper import scrape_single_company, scrape_all_companies

router = APIRouter(prefix="/scraper", tags=["scraper"])


@router.post("/run")
async def run_scraper(background_tasks: BackgroundTasks):
    background_tasks.add_task(scrape_all_companies)
    return {"status": "started", "message": "Scraping all companies in background"}


@router.post("/run/{company_id}")
async def run_scraper_for_company(company_id: int):
    result = await scrape_single_company(company_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/status")
async def scraper_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            func.count(Company.id).label("total"),
            func.count(Company.last_scraped_at).label("scraped"),
            func.count(Company.scrape_status).label("has_status"),
        ).where(Company.is_active == True)
    )
    row = result.one()

    recent = await db.execute(
        select(Company.name, Company.last_scraped_at, Company.scrape_status)
        .where(Company.last_scraped_at.isnot(None))
        .order_by(Company.last_scraped_at.desc())
        .limit(10)
    )
    recent_scrapes = [
        {"name": r.name, "last_scraped_at": r.last_scraped_at.isoformat() if r.last_scraped_at else None, "status": r.scrape_status}
        for r in recent.all()
    ]

    return {
        "total_companies": row.total,
        "scraped_at_least_once": row.scraped,
        "recent_scrapes": recent_scrapes,
    }