"""cashless qr extensions

Revision ID: 4c78f0ad6d36
Revises: b7a1e2f34d56
Create Date: 2026-02-20 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4c78f0ad6d36'
down_revision: Union[str, None] = 'b7a1e2f34d56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE qr_tokens ADD COLUMN IF NOT EXISTS provider_id UUID")
    op.execute("ALTER TABLE qr_tokens ADD COLUMN IF NOT EXISTS status VARCHAR(32)")
    op.execute("ALTER TABLE qr_tokens ADD COLUMN IF NOT EXISTS estimate_data JSONB")
    op.execute("ALTER TABLE qr_tokens ADD COLUMN IF NOT EXISTS patient_name VARCHAR(255)")
    op.execute("ALTER TABLE qr_tokens ADD COLUMN IF NOT EXISTS procedure_name VARCHAR(255)")
    op.execute("ALTER TABLE qr_tokens ADD COLUMN IF NOT EXISTS hospital_name VARCHAR(255)")
    op.execute("ALTER TABLE qr_tokens ADD COLUMN IF NOT EXISTS insurer_notes TEXT")
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_qr_tokens_provider_id'
            ) THEN
                ALTER TABLE qr_tokens ADD CONSTRAINT fk_qr_tokens_provider_id
                    FOREIGN KEY (provider_id) REFERENCES users(id);
            END IF;
        END $$
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_qr_tokens_provider_id ON qr_tokens(provider_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_qr_tokens_status ON qr_tokens(status)")


def downgrade() -> None:
    op.drop_index('ix_qr_tokens_status', table_name='qr_tokens')
    op.drop_index('ix_qr_tokens_provider_id', table_name='qr_tokens')
    op.drop_constraint('fk_qr_tokens_provider_id', 'qr_tokens', type_='foreignkey')
    op.drop_column('qr_tokens', 'insurer_notes')
    op.drop_column('qr_tokens', 'hospital_name')
    op.drop_column('qr_tokens', 'procedure_name')
    op.drop_column('qr_tokens', 'patient_name')
    op.drop_column('qr_tokens', 'estimate_data')
    op.drop_column('qr_tokens', 'status')
    op.drop_column('qr_tokens', 'provider_id')
