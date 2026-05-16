from datetime import datetime

from pydantic import BaseModel


class JobBase(BaseModel):
    title: str
    url: str
    location: str | None = None
    job_type: str | None = None
    seniority: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    is_remote: bool | None = None
    source: str = "ats_direct"


class JobCreate(JobBase):
    company_id: int
    description: str | None = None
    requirements: dict | None = None
    responsibilities: dict | None = None
    posted_at: datetime | None = None
    content_hash: str | None = None


class JobOut(JobBase):
    id: int
    company_id: int
    description: str | None = None
    requirements: dict | None = None
    responsibilities: dict | None = None
    posted_at: datetime | None = None
    discovered_at: datetime
    is_active: bool
    created_at: datetime
    company_name: str | None = None

    model_config = {"from_attributes": True}


class JobList(BaseModel):
    jobs: list[JobOut]
    total: int