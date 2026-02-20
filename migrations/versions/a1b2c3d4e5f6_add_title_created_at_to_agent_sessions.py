"""add title and created_at to agent_sessions

Revision ID: a1b2c3d4e5f6
Revises: 4c78f0ad6d36
Create Date: 2026-02-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "4c78f0ad6d36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use IF NOT EXISTS so the migration is safe to run even when columns were
    # added manually or by a previous partial run.
    op.execute(
        "ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS title VARCHAR(200)"
    )
    op.execute(
        "ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE"
    )
    # Back-fill created_at from updated_at for existing rows
    op.execute(
        "UPDATE agent_sessions SET created_at = updated_at WHERE created_at IS NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE agent_sessions DROP COLUMN IF EXISTS title")
    op.execute("ALTER TABLE agent_sessions DROP COLUMN IF EXISTS created_at")
