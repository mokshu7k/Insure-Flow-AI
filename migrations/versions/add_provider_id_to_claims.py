"""add provider_id to claims (merge heads)

Revision ID: b7a1e2f34d56
Revises: 3c0e82e1d503, cdfe9f7e2021
Create Date: 2026-02-20 19:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7a1e2f34d56'
down_revision: Union[str, None] = 'cdfe9f7e2021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE claims ADD COLUMN IF NOT EXISTS provider_id UUID")
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_claims_provider_id'
            ) THEN
                ALTER TABLE claims ADD CONSTRAINT fk_claims_provider_id
                    FOREIGN KEY (provider_id) REFERENCES users(id);
            END IF;
        END $$
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_claims_provider_id ON claims(provider_id)")


def downgrade() -> None:
    op.drop_index('ix_claims_provider_id', table_name='claims')
    op.drop_constraint('fk_claims_provider_id', 'claims', type_='foreignkey')
    op.drop_column('claims', 'provider_id')
