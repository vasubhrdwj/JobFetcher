"""widen title and scrape_status columns

Revision ID: 002_widen_columns
Revises: 001_lifecycle
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa


revision = "002_widen_columns"
down_revision = "001_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("jobs", "title",
                    existing_type=sa.String(512),
                    type_=sa.String(1024),
                    existing_nullable=False)
    op.alter_column("companies", "scrape_status",
                    existing_type=sa.String(256),
                    type_=sa.String(1024),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column("companies", "scrape_status",
                    existing_type=sa.String(1024),
                    type_=sa.String(256),
                    existing_nullable=True)
    op.alter_column("jobs", "title",
                    existing_type=sa.String(1024),
                    type_=sa.String(512),
                    existing_nullable=False)