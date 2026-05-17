"""initial schema

Revision ID: 000_initial
Revises:
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa


revision = "000_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("career_url", sa.String(1024), nullable=False),
        sa.Column("ats_platform", sa.Enum("greenhouse", "lever", "workday", "icims", "ashby", "custom", name="atsplatform"), nullable=True),
        sa.Column("industry", sa.String(128), nullable=True),
        sa.Column("logo_url", sa.String(1024), nullable=True),
        sa.Column("headquarters", sa.String(255), nullable=True),
        sa.Column("size", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=True),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scrape_status", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), index=True, nullable=False),
        sa.Column("title", sa.String(512), index=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("job_type", sa.String(64), nullable=True),
        sa.Column("seniority", sa.String(64), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("requirements", sa.JSON(), nullable=True),
        sa.Column("responsibilities", sa.JSON(), nullable=True),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("source", sa.String(64), server_default="ats_direct", nullable=True),
        sa.Column("is_remote", sa.Boolean(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("content_hash", sa.String(64), index=True, nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("target_role", sa.String(255), nullable=True),
        sa.Column("target_companies", sa.JSON(), nullable=True),
        sa.Column("target_locations", sa.JSON(), nullable=True),
        sa.Column("min_salary", sa.Integer(), nullable=True),
        sa.Column("skills", sa.JSON(), nullable=True),
        sa.Column("experience_years", sa.Integer(), nullable=True),
        sa.Column("education", sa.JSON(), nullable=True),
        sa.Column("resume_text", sa.Text(), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_profiles.id"), index=True, nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), index=True, nullable=False),
        sa.Column("status", sa.Enum("saved", "applied", "interviewing", "offer", "rejected", "withdrawn", name="applicationstatus"), server_default="saved", nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("applications")
    op.drop_table("user_profiles")
    op.drop_table("jobs")
    op.drop_table("companies")