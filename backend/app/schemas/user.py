from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserProfileBase(BaseModel):
    name: str | None = None
    email: EmailStr
    target_role: str | None = None
    target_companies: list[str] | None = None
    target_locations: list[str] | None = None
    min_salary: int | None = None
    skills: list[str] | None = None
    experience_years: int | None = None
    education: dict | None = None
    resume_text: str | None = None
    preferences: dict | None = None


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileOut(UserProfileBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}