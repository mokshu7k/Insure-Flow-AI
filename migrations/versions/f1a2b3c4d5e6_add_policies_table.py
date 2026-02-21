"""add_policies_table

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-02-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("policy_number", sa.String(length=128), nullable=False),
        sa.Column("policy_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sum_insured", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("premium_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("insured_name", sa.String(length=256), nullable=True),
        sa.Column("insured_dob", sa.Date(), nullable=True),
        sa.Column("nominee_name", sa.String(length=256), nullable=True),
        sa.Column("meta_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_number"),
    )
    op.create_index("ix_policies_user_id", "policies", ["user_id"], unique=False)
    op.create_index("ix_policies_policy_number", "policies", ["policy_number"], unique=False)
    op.create_index("ix_policies_status", "policies", ["status"], unique=False)
    op.create_index("ix_policies_policy_type", "policies", ["policy_type"], unique=False)

    # Add policy_id FK to claims (nullable — old claims won't have it)
    op.add_column("claims", sa.Column("policy_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_claims_policy_id", "claims", "policies", ["policy_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_claims_policy_id", "claims", ["policy_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_claims_policy_id", table_name="claims")
    op.drop_constraint("fk_claims_policy_id", "claims", type_="foreignkey")
    op.drop_column("claims", "policy_id")

    op.drop_index("ix_policies_policy_type", table_name="policies")
    op.drop_index("ix_policies_status", table_name="policies")
    op.drop_index("ix_policies_policy_number", table_name="policies")
    op.drop_index("ix_policies_user_id", table_name="policies")
    op.drop_table("policies")
