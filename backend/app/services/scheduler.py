import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.services.scraper import scrape_all_companies

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_scrape():
    logger.info(f"Starting scheduled scrape at {datetime.now(timezone.utc).isoformat()}")
    try:
        result = await scrape_all_companies()
        logger.info(f"Scheduled scrape complete: {result}")
    except Exception as e:
        logger.error(f"Scheduled scrape failed: {e}")


def start_scheduler():
    interval_hours = settings.SCRAPE_INTERVAL_HOURS or 3

    scheduler.add_job(
        scheduled_scrape,
        trigger=IntervalTrigger(hours=interval_hours),
        id="scrape_all_companies",
        name="Scrape all company career pages",
        replace_existing=True,
    )

    logger.info(f"Scheduler started: scraping every {interval_hours} hours")
    scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")