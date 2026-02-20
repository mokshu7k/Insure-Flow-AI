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
    # Add provider_id column to claims table
    op.add_column('claims', sa.Column('provider_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_claims_provider_id', 'claims', 'users',
        ['provider_id'], ['id']
    )
    op.create_index('ix_claims_provider_id', 'claims', ['provider_id'])


def downgrade() -> None:
    op.drop_index('ix_claims_provider_id', table_name='claims')
    op.drop_constraint('fk_claims_provider_id', 'claims', type_='foreignkey')
    op.drop_column('claims', 'provider_id')
