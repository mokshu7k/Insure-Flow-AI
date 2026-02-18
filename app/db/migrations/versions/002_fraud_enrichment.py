"""
002 -- Add user_fraud_profile table and feature_snapshot_json column.

Revision ID: 002_fraud_enrichment
Revises: 001_initial_schema
Create Date: 2026-02-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = "002_fraud_enrichment"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Part 1: Create user_fraud_profile table ---
    op.create_table(
        "user_fraud_profile",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("recent_claim_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prior_fraud_flags", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_fraud_profile_user_id", "user_fraud_profile", ["user_id"], unique=True)

    # --- Part 6: Add feature_snapshot_json to fraud_assessments ---
    op.add_column(
        "fraud_assessments",
        sa.Column("feature_snapshot_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fraud_assessments", "feature_snapshot_json")
    op.drop_index("ix_user_fraud_profile_user_id", table_name="user_fraud_profile")
    op.drop_table("user_fraud_profile")
