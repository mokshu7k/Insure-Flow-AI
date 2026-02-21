"""schema overhaul: multi-tenant, flexible policy types, document pipeline

Creates:
  - insurers
  - policy_types
  - document_requirements
  - kyc_documents
  - policy_nominees
  - policy_documents
  - claim_documents
  - document_validation_results
  - claim_status_history

Alters:
  - users:    +insurer_id, +insurer_customer_id, +full_name, +phone, +date_of_birth, +gender, +address
  - policies: +insurer_id, +policy_type_id, +deductible, +copay_percentage, +coverage_details,
              +policy_schedule, +terms_conditions_version, +terms_conditions_ref,
              +first_premium_receipt_ref, +type_specific_data
  - claims:   +claim_number, +approved_amount, +incident_date, +situation_details,
              +total_docs_required, +total_docs_submitted, +total_docs_validated

Revision ID: g0001_schema_overhaul
Revises: f1a2b3c4d5e6
Create Date: 2026-02-21
"""
from __future__ import annotations

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "g0001_schema_overhaul"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. insurers ──────────────────────────────────────────────────────────
    op.create_table(
        "insurers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("registration_number", sa.String(128), unique=True, nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(32), nullable=True),
        sa.Column("website", sa.String(512), nullable=True),
        sa.Column("logo_url", sa.Text, nullable=True),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_insurers_code", "insurers", ["code"])
    op.create_index("ix_insurers_is_active", "insurers", ["is_active"])

    # ── 2. policy_types ──────────────────────────────────────────────────────
    op.create_table(
        "policy_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("insurer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("insurers.id"), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("code", sa.String(128), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_policy_types_insurer_id", "policy_types", ["insurer_id"])
    op.create_index("ix_policy_types_category", "policy_types", ["category"])
    op.create_index("uq_policy_types_insurer_code", "policy_types", ["insurer_id", "code"], unique=True)

    # ── 3. document_requirements ─────────────────────────────────────────────
    op.create_table(
        "document_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_types.id"), nullable=False),
        sa.Column("document_type_code", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("is_compulsory", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("extraction_template", postgresql.JSONB, nullable=True),
        sa.Column("validation_rules", postgresql.JSONB, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("instructions", sa.Text, nullable=True),
        sa.Column("allowed_mime_types", postgresql.JSONB, nullable=True),
        sa.Column("max_file_size_mb", sa.Integer, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_doc_req_policy_type_id", "document_requirements", ["policy_type_id"])
    op.create_index("uq_doc_req_type_doc", "document_requirements", ["policy_type_id", "document_type_code"], unique=True)

    # ── 4. Alter users (add insurer link + personal details) ─────────────────
    op.add_column("users", sa.Column("insurer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("insurers.id"), nullable=True))
    op.add_column("users", sa.Column("insurer_customer_id", sa.String(128), nullable=True))
    op.add_column("users", sa.Column("full_name", sa.String(256), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("date_of_birth", sa.Date, nullable=True))
    op.add_column("users", sa.Column("gender", sa.String(16), nullable=True))
    op.add_column("users", sa.Column("address", postgresql.JSONB, nullable=True))
    op.create_index("ix_users_insurer_id", "users", ["insurer_id"])
    # Partial unique: one insurer_customer_id per insurer
    op.execute(
        "CREATE UNIQUE INDEX uq_users_insurer_customer_id "
        "ON users (insurer_id, insurer_customer_id) "
        "WHERE insurer_customer_id IS NOT NULL"
    )

    # ── 5. kyc_documents ─────────────────────────────────────────────────────
    op.create_table(
        "kyc_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("document_number", sa.String(256), nullable=True),
        sa.Column("document_data", postgresql.JSONB, nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_source", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_kyc_user_id", "kyc_documents", ["user_id"])
    op.create_index("ix_kyc_doc_type", "kyc_documents", ["document_type"])
    op.execute(
        "CREATE UNIQUE INDEX uq_kyc_user_doctype_active "
        "ON kyc_documents (user_id, document_type) "
        "WHERE is_active = true"
    )

    # ── 6. Alter policies (add new fields) ───────────────────────────────────
    op.add_column("policies", sa.Column("insurer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("insurers.id"), nullable=True))
    op.add_column("policies", sa.Column("policy_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_types.id"), nullable=True))
    op.add_column("policies", sa.Column("deductible", sa.Numeric(14, 2), nullable=True))
    op.add_column("policies", sa.Column("copay_percentage", sa.Numeric(5, 2), nullable=True))
    op.add_column("policies", sa.Column("coverage_details", postgresql.JSONB, nullable=True))
    op.add_column("policies", sa.Column("policy_schedule", postgresql.JSONB, nullable=True))
    op.add_column("policies", sa.Column("terms_conditions_version", sa.String(64), nullable=True))
    op.add_column("policies", sa.Column("terms_conditions_ref", sa.Text, nullable=True))
    op.add_column("policies", sa.Column("first_premium_receipt_ref", sa.Text, nullable=True))
    op.add_column("policies", sa.Column("type_specific_data", postgresql.JSONB, nullable=True))
    op.create_index("ix_policies_insurer_id", "policies", ["insurer_id"])
    op.create_index("ix_policies_policy_type_id", "policies", ["policy_type_id"])

    # ── 7. policy_nominees ───────────────────────────────────────────────────
    op.create_table(
        "policy_nominees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(256), nullable=False),
        sa.Column("relationship_to_insured", sa.String(64), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("share_percentage", sa.Numeric(5, 2), nullable=False, server_default="100"),
        sa.Column("contact_info", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_policy_nominees_policy_id", "policy_nominees", ["policy_id"])

    # ── 8. policy_documents ──────────────────────────────────────────────────
    op.create_table(
        "policy_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type_code", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.Text, nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("extracted_data", postgresql.JSONB, nullable=True),
        sa.Column("verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_policy_docs_policy_id", "policy_documents", ["policy_id"])
    op.create_index("ix_policy_docs_type", "policy_documents", ["document_type_code"])

    # ── 9. Alter claims (add new fields) ─────────────────────────────────────
    op.add_column("claims", sa.Column("claim_number", sa.String(64), nullable=True))
    op.add_column("claims", sa.Column("approved_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("claims", sa.Column("incident_date", sa.Date, nullable=True))
    op.add_column("claims", sa.Column("situation_details", postgresql.JSONB, nullable=True))
    op.add_column("claims", sa.Column("total_docs_required", sa.Integer, nullable=True))
    op.add_column("claims", sa.Column("total_docs_submitted", sa.Integer, nullable=True))
    op.add_column("claims", sa.Column("total_docs_validated", sa.Integer, nullable=True))

    # Back-fill claim_number for existing rows with the claim id as a fallback
    op.execute("UPDATE claims SET claim_number = 'CLM-' || SUBSTRING(id::text, 1, 8) WHERE claim_number IS NULL")
    op.alter_column("claims", "claim_number", nullable=False)
    op.create_index("ix_claims_claim_number", "claims", ["claim_number"], unique=True)
    # ix_claims_policy_id already exists from f1a2b3c4d5e6_add_policies_table migration

    # ── 10. claim_documents ──────────────────────────────────────────────────
    op.create_table(
        "claim_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("uploader_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_requirement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_requirements.id"), nullable=True),
        sa.Column("document_type_code", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.Text, nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(128), nullable=True),
        # OCR
        sa.Column("ocr_status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("extracted_data", postgresql.JSONB, nullable=True),
        sa.Column("extraction_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("extraction_template_used", postgresql.JSONB, nullable=True),
        # KYC match
        sa.Column("kyc_match_status", sa.String(32), nullable=False, server_default="NOT_APPLICABLE"),
        sa.Column("kyc_match_details", postgresql.JSONB, nullable=True),
        # Promoted columns (copied from extracted_data for cross-doc queries)
        sa.Column("patient_name", sa.String(256), nullable=True),
        sa.Column("hospital_name", sa.String(256), nullable=True),
        sa.Column("doctor_name", sa.String(256), nullable=True),
        sa.Column("diagnosis", sa.Text, nullable=True),
        sa.Column("admission_date", sa.Date, nullable=True),
        sa.Column("discharge_date", sa.Date, nullable=True),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("document_date", sa.Date, nullable=True),
        sa.Column("document_number", sa.String(128), nullable=True),
        sa.Column("entity_gstin", sa.String(15), nullable=True),
        sa.Column("entity_registration_no", sa.String(128), nullable=True),
        # Validation
        sa.Column("validation_status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("validation_reason", sa.Text, nullable=True),
        sa.Column("missing_fields", postgresql.JSONB, nullable=True),
        # Fraud
        sa.Column("authenticity_metadata", postgresql.JSONB, nullable=True),
        sa.Column("fraud_signal_weight", sa.Numeric(5, 4), nullable=True),
        sa.Column("requires_manual_review", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_claim_docs_claim_id", "claim_documents", ["claim_id"])
    op.create_index("ix_claim_docs_uploader_id", "claim_documents", ["uploader_id"])
    op.create_index("ix_claim_docs_validation_status", "claim_documents", ["validation_status"])
    op.create_index("ix_claim_docs_ocr_status", "claim_documents", ["ocr_status"])
    op.create_index("ix_claim_docs_patient_name", "claim_documents", ["patient_name"])
    op.create_index("ix_claim_docs_hospital_name", "claim_documents", ["hospital_name"])

    # ── 11. document_validation_results ──────────────────────────────────────
    op.create_table(
        "document_validation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claim_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("validation_type", sa.String(64), nullable=False),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_val_results_doc_id", "document_validation_results", ["claim_document_id"])
    op.create_index("ix_val_results_type", "document_validation_results", ["validation_type"])

    # ── 12. claim_status_history ─────────────────────────────────────────────
    op.create_table(
        "claim_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_claim_status_history_claim_id", "claim_status_history", ["claim_id"])
    op.create_index("ix_claim_status_history_created_at", "claim_status_history", ["created_at"])


def downgrade() -> None:
    # ── Drop new tables ──
    op.drop_table("claim_status_history")
    op.drop_table("document_validation_results")
    op.drop_table("claim_documents")
    op.drop_table("policy_documents")
    op.drop_table("policy_nominees")
    op.drop_table("kyc_documents")
    op.drop_table("document_requirements")
    op.drop_table("policy_types")

    # ── Remove new columns from claims ──
    # ix_claims_policy_id is managed by f1a2b3c4d5e6_add_policies_table, not dropped here
    op.drop_index("ix_claims_claim_number", table_name="claims")
    op.drop_column("claims", "total_docs_validated")
    op.drop_column("claims", "total_docs_submitted")
    op.drop_column("claims", "total_docs_required")
    op.drop_column("claims", "situation_details")
    op.drop_column("claims", "incident_date")
    op.drop_column("claims", "approved_amount")
    op.drop_column("claims", "claim_number")

    # ── Remove new columns from policies ──
    op.drop_index("ix_policies_policy_type_id", table_name="policies")
    op.drop_index("ix_policies_insurer_id", table_name="policies")
    op.drop_column("policies", "type_specific_data")
    op.drop_column("policies", "first_premium_receipt_ref")
    op.drop_column("policies", "terms_conditions_ref")
    op.drop_column("policies", "terms_conditions_version")
    op.drop_column("policies", "policy_schedule")
    op.drop_column("policies", "coverage_details")
    op.drop_column("policies", "copay_percentage")
    op.drop_column("policies", "deductible")
    op.drop_column("policies", "policy_type_id")
    op.drop_column("policies", "insurer_id")

    # ── Remove new columns from users ──
    op.execute("DROP INDEX IF EXISTS uq_users_insurer_customer_id")
    op.drop_index("ix_users_insurer_id", table_name="users")
    op.drop_column("users", "address")
    op.drop_column("users", "gender")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "phone")
    op.drop_column("users", "full_name")
    op.drop_column("users", "insurer_customer_id")
    op.drop_column("users", "insurer_id")

    # ── Drop insurers last (FK dependencies) ──
    op.drop_table("insurers")
