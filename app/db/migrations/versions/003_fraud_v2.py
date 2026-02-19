"""
003 -- Fraud engine v2: new columns across fraud_assessments, user_fraud_profile, and claims.

Changes
-------
fraud_assessments
  + risk_level            VARCHAR(20)
  + behavioral_flags_json JSON
  + document_flags_json   JSON
  + network_flags_json    JSON
  + config_version        VARCHAR(20)
  + baseline_version      VARCHAR(20)
  + ai_degraded_mode      BOOLEAN
  + ml_model_used         BOOLEAN

user_fraud_profile
  + confirmed_fraud_count INTEGER  default 0
  + last_claim_date       TIMESTAMP
  + total_claim_amount_90d FLOAT

claims
  + provider_id           UUID (FK → users.id)
  + policy_expiry_date    DATE

Revision ID: 003_fraud_v2
Revises: 002_fraud_enrichment
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_fraud_v2"
down_revision = "002_fraud_enrichment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── fraud_assessments new columns ──────────────────────────────────
    op.add_column("fraud_assessments",
        sa.Column("risk_level", sa.String(20), nullable=True))
    op.add_column("fraud_assessments",
        sa.Column("behavioral_flags_json", sa.JSON(), nullable=True))
    op.add_column("fraud_assessments",
        sa.Column("document_flags_json", sa.JSON(), nullable=True))
    op.add_column("fraud_assessments",
        sa.Column("network_flags_json", sa.JSON(), nullable=True))
    op.add_column("fraud_assessments",
        sa.Column("config_version", sa.String(20), nullable=True))
    op.add_column("fraud_assessments",
        sa.Column("baseline_version", sa.String(20), nullable=True))
    op.add_column("fraud_assessments",
        sa.Column("ai_degraded_mode", sa.Boolean(), nullable=True, server_default="false"))
    op.add_column("fraud_assessments",
        sa.Column("ml_model_used", sa.Boolean(), nullable=True, server_default="false"))

    # ── user_fraud_profile new columns ─────────────────────────────────
    op.add_column("user_fraud_profile",
        sa.Column("confirmed_fraud_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user_fraud_profile",
        sa.Column("last_claim_date", sa.DateTime(), nullable=True))
    op.add_column("user_fraud_profile",
        sa.Column("total_claim_amount_90d", sa.Float(), nullable=True))

    # ── claims new columns ─────────────────────────────────────────────
    op.add_column("claims",
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        )
    )
    op.create_index("ix_claims_provider_id", "claims", ["provider_id"])
    op.add_column("claims",
        sa.Column("policy_expiry_date", sa.Date(), nullable=True))


def downgrade() -> None:
    # claims
    op.drop_index("ix_claims_provider_id", table_name="claims")
    op.drop_column("claims", "provider_id")
    op.drop_column("claims", "policy_expiry_date")

    # user_fraud_profile
    op.drop_column("user_fraud_profile", "total_claim_amount_90d")
    op.drop_column("user_fraud_profile", "last_claim_date")
    op.drop_column("user_fraud_profile", "confirmed_fraud_count")

    # fraud_assessments
    op.drop_column("fraud_assessments", "ml_model_used")
    op.drop_column("fraud_assessments", "ai_degraded_mode")
    op.drop_column("fraud_assessments", "baseline_version")
    op.drop_column("fraud_assessments", "config_version")
    op.drop_column("fraud_assessments", "network_flags_json")
    op.drop_column("fraud_assessments", "document_flags_json")
    op.drop_column("fraud_assessments", "behavioral_flags_json")
    op.drop_column("fraud_assessments", "risk_level")
