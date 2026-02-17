"""Initial schema: all tables

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-01-01 00:00:00.000000

Every column here matches its SQLAlchemy model exactly.
audit_logs and document_access_logs have NO updated_at (immutable).
All other tables have created_at + updated_at from BaseModel.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ── users ─────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email",         sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role",          sa.String(50),  nullable=False),
        sa.Column("is_active",     sa.Boolean(),   nullable=False, server_default="true"),
        sa.Column("created_at",    sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",    sa.DateTime(),  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id",    "users", ["id"])

    # ── user_consents  (immutable rows but has updated_at for BaseModel compat) ──
    op.create_table(
        "user_consents",
        sa.Column("id",                 postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",            postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consent_version",    sa.String(50),  nullable=False),
        sa.Column("consent_text_hash",  sa.String(64),  nullable=False),
        sa.Column("timestamp",          sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("created_at",         sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",         sa.DateTime(),  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_consents_user_id", "user_consents", ["user_id"])

    # ── claims ────────────────────────────────────────────────────────────
    op.create_table(
        "claims",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_number", sa.String(100), nullable=False),
        sa.Column("user_id",       postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("claim_type",    sa.String(50),  nullable=False),
        sa.Column("claim_amount",  sa.Float(),     nullable=False),
        sa.Column("status",        sa.String(50),  nullable=False, server_default="SUBMITTED"),
        sa.Column("fraud_score",   sa.Float(),     nullable=True),
        sa.Column("created_at",    sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",    sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("claim_amount > 0", name="ck_claims_positive_amount"),
        sa.CheckConstraint(
            "status IN ('SUBMITTED','OCR_PROCESSED','FRAUD_ANALYZED',"
            "'MANUAL_REVIEW_REQUIRED','APPROVED','REJECTED','SETTLED')",
            name="ck_claims_valid_status",
        ),
        sa.CheckConstraint(
            "claim_type IN ('HEALTH','MOTOR','REIMBURSEMENT')",
            name="ck_claims_valid_type",
        ),
    )
    op.create_index("ix_claims_id",            "claims", ["id"])
    op.create_index("ix_claims_user_id",       "claims", ["user_id"])
    op.create_index("ix_claims_policy_number", "claims", ["policy_number"])
    op.create_index("ix_claims_status",        "claims", ["status"])

    # ── documents ─────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id",                  postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_id",            postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("file_path",           sa.String(500), nullable=False),
        sa.Column("document_type",       sa.String(50),  nullable=False),
        sa.Column("ocr_extracted_json",  postgresql.JSONB(), nullable=True),
        sa.Column("created_at",          sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",          sa.DateTime(),  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_documents_claim_id", "documents", ["claim_id"])

    # ── fraud_assessments ─────────────────────────────────────────────────
    op.create_table(
        "fraud_assessments",
        sa.Column("id",                        postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_id",                  postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("fraud_score",               sa.Float(),  nullable=False),
        sa.Column("deterministic_signals_json", postgresql.JSONB(), nullable=False),
        sa.Column("statistical_signals_json",   postgresql.JSONB(), nullable=False),
        sa.Column("explanation_text",           sa.Text(),   nullable=False),
        sa.Column("created_at",                sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",                sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "fraud_score >= 0 AND fraud_score <= 1", name="ck_fraud_score_range"
        ),
    )
    op.create_index("ix_fraud_assessments_claim_id", "fraud_assessments", ["claim_id"])

    # ── qr_authorizations ─────────────────────────────────────────────────
    op.create_table(
        "qr_authorizations",
        sa.Column("id",             postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_id",       postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("provider_id",    postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_limit", sa.Float(),   nullable=False),
        sa.Column("qr_token_hash",  sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at",     sa.DateTime(), nullable=False),
        sa.Column("is_consumed",    sa.Boolean(),  nullable=False, server_default="false"),
        sa.Column("created_at",     sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",     sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("approved_limit > 0", name="ck_qr_positive_limit"),
    )
    op.create_index("ix_qr_authorizations_claim_id",   "qr_authorizations", ["claim_id"])
    op.create_index("ix_qr_authorizations_token_hash", "qr_authorizations", ["qr_token_hash"], unique=True)

    # ── settlements ───────────────────────────────────────────────────────
    op.create_table(
        "settlements",
        sa.Column("id",                      postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_id",                postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("settlement_reference_id", sa.String(255), nullable=False, unique=True),
        sa.Column("amount",                  sa.Float(),     nullable=False),
        sa.Column("status",                  sa.String(50),  nullable=False, server_default="PENDING"),
        sa.Column("created_at",              sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",              sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('PENDING','PROCESSING','COMPLETED','FAILED')",
            name="ck_settlements_valid_status",
        ),
    )
    op.create_index("ix_settlements_claim_id", "settlements", ["claim_id"])

    # ── audit_logs  (IMMUTABLE — no updated_at) ───────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id",      postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action_type",   sa.String(100), nullable=False),
        sa.Column("entity_type",   sa.String(100), nullable=False),
        sa.Column("entity_id",     postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("timestamp",     sa.DateTime(), nullable=False, server_default=sa.func.now()),
        # NO created_at / updated_at — AuditLog extends Base not BaseModel
    )
    op.create_index("ix_audit_logs_actor_id",    "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_entity_id",   "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_action_type", "audit_logs", ["action_type"])
    op.create_index("ix_audit_logs_timestamp",   "audit_logs", ["timestamp"])

    # Immutability trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Modification of audit_logs is not permitted';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
    """)

    # ── document_access_logs  (IMMUTABLE — no updated_at) ─────────────────
    op.create_table(
        "document_access_logs",
        sa.Column("id",          postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",     postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("action",      sa.String(50),  nullable=False),
        sa.Column("timestamp",   sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        # NO created_at / updated_at — DocumentAccessLog extends Base not BaseModel
    )
    op.create_index("ix_doc_access_user_id",     "document_access_logs", ["user_id"])
    op.create_index("ix_doc_access_document_id", "document_access_logs", ["document_id"])
    op.create_index("ix_doc_access_timestamp",   "document_access_logs", ["timestamp"])

    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_access_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Modification of document_access_logs is not permitted';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER doc_access_logs_immutable
        BEFORE UPDATE OR DELETE ON document_access_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_access_log_modification();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS doc_access_logs_immutable ON document_access_logs;")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS prevent_access_log_modification;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_modification;")
    op.drop_table("document_access_logs")
    op.drop_table("audit_logs")
    op.drop_table("settlements")
    op.drop_table("qr_authorizations")
    op.drop_table("fraud_assessments")
    op.drop_table("documents")
    op.drop_table("claims")
    op.drop_table("user_consents")
    op.drop_table("users")