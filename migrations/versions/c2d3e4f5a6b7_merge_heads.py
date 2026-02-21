"""merge all heads into one

Revision ID: c2d3e4f5a6b7
Revises: b2c3d4e5f6a7, d4e5f6a7b8c9
Create Date: 2026-02-21

"""
from alembic import op

revision = "c2d3e4f5a6b7"
down_revision = ("b2c3d4e5f6a7", "d4e5f6a7b8c9")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
