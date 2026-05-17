import enum
from datetime import datetime

from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime, ForeignKey, Enum, JSON,
    func, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ATSPlatform(str, enum.Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    ICIMS = "icims"
    ASHBY = "ashby"
    CUSTOM = "custom"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    career_url: Mapped[str] = mapped_column(String(1024))
    ats_platform: Mapped[ATSPlatform] = mapped_column(Enum(ATSPlatform), default=ATSPlatform.CUSTOM)
    ats_slug: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(128))
    logo_url: Mapped[str | None] = mapped_column(String(1024))
    headquarters: Mapped[str | None] = mapped_column(String(255))
    size: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scrape_status: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    jobs: Mapped[list["Job"]] = relationship(back_populates="company")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("company_id", "url", name="uq_job_company_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), index=True)
    title: Mapped[str] = mapped_column(String(512), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    job_type: Mapped[str | None] = mapped_column(String(64))
    seniority: Mapped[str | None] = mapped_column(String(64))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    requirements: Mapped[dict | None] = mapped_column(JSON)
    responsibilities: Mapped[dict | None] = mapped_column(JSON)
    url: Mapped[str] = mapped_column(String(1024))
    source: Mapped[str] = mapped_column(String(64), default="ats_direct")
    is_remote: Mapped[bool | None] = mapped_column(Boolean)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    company: Mapped["Company"] = relationship(back_populates="jobs")
    applications: Mapped[list["Application"]] = relationship(back_populates="job")


class ApplicationStatus(str, enum.Enum):
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    target_role: Mapped[str | None] = mapped_column(String(255))
    target_companies: Mapped[dict | None] = mapped_column(JSON)
    target_locations: Mapped[dict | None] = mapped_column(JSON)
    min_salary: Mapped[int | None] = mapped_column(Integer)
    skills: Mapped[dict | None] = mapped_column(JSON)
    experience_years: Mapped[int | None] = mapped_column(Integer)
    education: Mapped[dict | None] = mapped_column(JSON)
    resume_text: Mapped[str | None] = mapped_column(Text)
    preferences: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    applications: Mapped[list["Application"]] = relationship(back_populates="user")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_profiles.id"), index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), index=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.SAVED
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    match_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["UserProfile"] = relationship(back_populates="applications")
    job: Mapped["Job"] = relationship(back_populates="applications")