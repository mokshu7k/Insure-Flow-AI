"""add ai_report to claims

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-21
"""
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE claims ADD COLUMN IF NOT EXISTS ai_report TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE claims DROP COLUMN IF EXISTS ai_report")
