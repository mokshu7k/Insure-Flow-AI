"""ClaimDocument ORM model — documents submitted by the user for a claim.

Each document goes through an OCR → validation → KYC-match pipeline.
This model tracks the full lifecycle of a claim-submitted document.

Storage strategy — HYBRID:
  * ``extracted_data`` (JSONB) holds the FULL extraction output matching
    the template's ``fields`` list. Every key the LLM returns lives here.
  * "Promoted" columns duplicate a few cross-document fields that appear
    on *most* document types and are used for:
      → cross-document consistency checks (patient_name must match across
        hospital bill, discharge summary, prescription, Aadhaar …)
      → SQL-level fraud queries (date ranges, amount sums)
      → dashboard aggregations without JSONB operators.
    The service layer copies these from ``extracted_data`` after OCR.
"""
from __future__ import annotations

import uuid
from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ClaimDocument(Base):
    __tablename__ = "claim_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False
    )
    uploader_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Links to the requirement that triggered this upload (nullable for ad-hoc)
    document_requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_requirements.id"), nullable=True
    )

    # ── File metadata ──
    document_type_code: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # ── OCR / Extraction ──
    ocr_status: Mapped[str] = mapped_column(
        String(32), default="PENDING", nullable=False
    )  # PENDING, PROCESSING, COMPLETED, FAILED

    extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # ^^ Full extraction output — shape matches extraction_template.fields.
    # Example for HOSPITAL_BILL:
    # {
    #   "hospital_name": "Apollo Hospital",
    #   "patient_name": "Rajesh Kumar",
    #   "admission_date": "15/01/2026",
    #   "discharge_date": "22/01/2026",
    #   "total_amount": 145000,
    #   "room_charges": 42000,
    #   "surgery_charges": 60000,
    #   ...
    #   "line_items": [{"description": "ICU bed", "quantity": 3, "rate": 14000, "amount": 42000}, ...]
    # }

    extraction_confidence: Mapped[float | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )

    # Snapshot of the template used at extraction time (for reproducibility)
    extraction_template_used: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PROMOTED COLUMNS — copied from extracted_data after OCR.
    # These are the fields that appear across multiple document types and
    # are used for cross-document consistency checks + SQL fraud queries.
    #
    # Which doc types populate which promoted column:
    #   patient_name     → ALL except Aadhaar/PAN (those use full_name)
    #   hospital_name    → HOSPITAL_BILL, DISCHARGE_SUMMARY, CLAIM_FORM, PREAUTH_LETTER
    #   doctor_name      → DISCHARGE_SUMMARY, PRESCRIPTION, CLAIM_FORM
    #   diagnosis        → DISCHARGE_SUMMARY, PRESCRIPTION, CLAIM_FORM, PREAUTH_LETTER
    #   admission_date   → HOSPITAL_BILL, DISCHARGE_SUMMARY, CLAIM_FORM
    #   discharge_date   → HOSPITAL_BILL, DISCHARGE_SUMMARY
    #   total_amount     → HOSPITAL_BILL, PHARMACY_BILL, AMBULANCE_RECEIPT
    #   document_date    → ALL (bill_date / report_date / prescription_date / etc.)
    #   document_number  → HOSPITAL_BILL(bill_number), LAB_REPORT(report_id),
    #                       AADHAAR(aadhaar_number), PAN(pan_number), FIR(fir_number)
    #   entity_gstin     → HOSPITAL_BILL, PHARMACY_BILL (for gov DB verification)
    #   entity_registration_no → HOSPITAL_BILL(ROHINI), DISCHARGE_SUMMARY, CLAIM_FORM
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    patient_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    hospital_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    doctor_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    admission_date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    discharge_date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )  # up to ₹99,99,99,99,999.99
    document_date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    entity_gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    entity_registration_no: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # ── KYC matching (for identity docs) ──
    kyc_match_status: Mapped[str] = mapped_column(
        String(32), default="NOT_APPLICABLE", nullable=False
    )  # PENDING, MATCHED, MISMATCHED, NOT_APPLICABLE
    kyc_match_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g. {"name_match": true, "dob_match": true, "number_match": false, ...}

    # ── Overall validation ──
    validation_status: Mapped[str] = mapped_column(
        String(32), default="PENDING", nullable=False
    )  # PENDING, ACCEPTED, REJECTED, NEEDS_RESUBMISSION, FLAGGED
    validation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g. ["date_of_birth", "address"] — fields the LLM couldn't find

    # ── Fraud / Authenticity ──
    authenticity_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fraud_signal_weight: Mapped[float | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )  # 0.0–1.0

    requires_manual_review: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ──
    claim = relationship("Claim", back_populates="claim_documents")
    uploader = relationship("User", foreign_keys=[uploader_id])
    document_requirement = relationship("DocumentRequirement")
    validation_results = relationship(
        "DocumentValidationResult",
        back_populates="claim_document",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_claim_docs_claim_id", "claim_id"),
        Index("ix_claim_docs_uploader_id", "uploader_id"),
        Index("ix_claim_docs_validation_status", "validation_status"),
        Index("ix_claim_docs_ocr_status", "ocr_status"),
        Index("ix_claim_docs_patient_name", "patient_name"),
        Index("ix_claim_docs_hospital_name", "hospital_name"),
    )
