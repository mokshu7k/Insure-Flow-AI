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
    # Add cashless-specific columns to qr_tokens
    op.add_column('qr_tokens', sa.Column('provider_id', sa.UUID(), nullable=True))
    op.add_column('qr_tokens', sa.Column('status', sa.String(length=32), nullable=True))
    op.add_column('qr_tokens', sa.Column('estimate_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('qr_tokens', sa.Column('patient_name', sa.String(length=255), nullable=True))
    op.add_column('qr_tokens', sa.Column('procedure_name', sa.String(length=255), nullable=True))
    op.add_column('qr_tokens', sa.Column('hospital_name', sa.String(length=255), nullable=True))
    op.add_column('qr_tokens', sa.Column('insurer_notes', sa.Text(), nullable=True))

    op.create_foreign_key(
        'fk_qr_tokens_provider_id', 'qr_tokens', 'users',
        ['provider_id'], ['id']
    )
    op.create_index('ix_qr_tokens_provider_id', 'qr_tokens', ['provider_id'])
    op.create_index('ix_qr_tokens_status', 'qr_tokens', ['status'])


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
