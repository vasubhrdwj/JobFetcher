from datetime import datetime

from pydantic import BaseModel

from app.models.models import ApplicationStatus


class ApplicationBase(BaseModel):
    user_id: int
    job_id: int
    status: ApplicationStatus = ApplicationStatus.SAVED
    notes: str | None = None
    match_score: float | None = None


class ApplicationCreate(ApplicationBase):
    applied_at: datetime | None = None
    next_follow_up_at: datetime | None = None


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = None
    next_follow_up_at: datetime | None = None
    match_score: float | None = None


class ApplicationOut(ApplicationBase):
    id: int
    applied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}