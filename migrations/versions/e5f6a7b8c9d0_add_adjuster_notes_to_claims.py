"""add adjuster_notes to claims

Revision ID: e5f6a7b8c9d0
Revises: b2c3d4e5f6a7
Create Date: 2026-02-21
"""
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE claims ADD COLUMN IF NOT EXISTS adjuster_notes TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE claims DROP COLUMN IF EXISTS adjuster_notes")
