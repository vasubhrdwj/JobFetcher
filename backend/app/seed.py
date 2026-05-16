import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.database import async_session, init_db
from app.models.models import Company, ATSPlatform


COMPANIES_FILE = Path(__file__).parent / "data" / "companies.json"


async def seed():
    await init_db()

    async with async_session() as session:
        existing = await session.execute(select(Company.name))
        existing_names = {row[0] for row in existing.all()}

        with open(COMPANIES_FILE) as f:
            companies_data = json.load(f)

        added = 0
        for entry in companies_data:
            if entry["name"] in existing_names:
                continue

            ats = ATSPlatform(entry["ats_platform"])
            company = Company(
                name=entry["name"],
                career_url=entry["career_url"],
                ats_platform=ats,
                industry=entry.get("industry"),
                headquarters=entry.get("headquarters"),
                size=entry.get("size"),
                is_active=True,
            )
            session.add(company)
            existing_names.add(entry["name"])
            added += 1

        await session.commit()
        print(f"Seeded {added} new companies ({len(existing_names)} unique names in DB).")


if __name__ == "__main__":
    asyncio.run(seed())