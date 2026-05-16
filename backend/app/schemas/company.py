from datetime import datetime

from pydantic import BaseModel, HttpUrl

from app.models.models import ATSPlatform


class CompanyBase(BaseModel):
    name: str
    career_url: str
    ats_platform: ATSPlatform = ATSPlatform.CUSTOM
    industry: str | None = None
    logo_url: str | None = None
    headquarters: str | None = None
    size: str | None = None
    is_active: bool = True


class CompanyCreate(CompanyBase):
    pass


class CompanyOut(CompanyBase):
    id: int
    last_scraped_at: datetime | None = None
    scrape_status: str | None = None
    created_at: datetime
    updated_at: datetime
    job_count: int = 0

    model_config = {"from_attributes": True}


class CompanyList(BaseModel):
    companies: list[CompanyOut]
    total: int