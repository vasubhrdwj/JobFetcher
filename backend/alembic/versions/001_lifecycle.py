"""add last_seen_at, ats_slug, widen scrape_status, unique company+url

Revision ID: 001_lifecycle
Revises:
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa


revision = "001_lifecycle"
down_revision = "000_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("companies", sa.Column("ats_slug", sa.String(255), nullable=True))

    op.alter_column("companies", "scrape_status", type_=sa.String(256), existing_type=sa.String(32))

    op.create_unique_constraint("uq_job_company_url", "jobs", ["company_id", "url"])


def downgrade() -> None:
    op.drop_constraint("uq_job_company_url", "jobs", type_="unique")

    op.alter_column("companies", "scrape_status", type_=sa.String(32), existing_type=sa.String(256))

    op.drop_column("companies", "ats_slug")
    op.drop_column("jobs", "last_seen_at")