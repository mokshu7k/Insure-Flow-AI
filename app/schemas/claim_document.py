"""ClaimDocument schemas — request/response models for the new ClaimDocument model."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, field_validator


class ClaimDocumentResponse(BaseModel):
    """Response schema for a ClaimDocument row.

    Intentionally compatible with the legacy DocumentResponse shape so the
    frontend wizard (step 4 review + EditableExtractedData) keeps working
    without changes:
      • ``document_type``             ← ``document_type_code``
      • ``validation_status``         ← same field
      • ``authenticity_metadata_json`` ← ``authenticity_metadata`` (renamed in model)
    """
    model_config = {"from_attributes": True}

    # ── Core ──
    id: uuid.UUID
    claim_id: uuid.UUID
    document_type_code: str
    document_type: str                           # alias — same value as document_type_code
    document_requirement_id: Optional[uuid.UUID]

    # ── File ──
    original_filename: Optional[str]
    content_type: Optional[str]
    storage_path: str
    gcs_path: Optional[str]  # GCS blob name; None when GCS is not configured

    # ── OCR / Extraction ──
    ocr_status: str                              # PENDING | PROCESSING | COMPLETED | FAILED
    extracted_data: Optional[dict[str, Any]]
    extraction_confidence: Optional[float]
    extraction_template_used: Optional[dict[str, Any]]

    # ── Promoted columns ──
    patient_name: Optional[str]
    hospital_name: Optional[str]
    doctor_name: Optional[str]
    diagnosis: Optional[str]
    admission_date: Optional[date]
    discharge_date: Optional[date]
    total_amount: Optional[Decimal]
    document_date: Optional[date]
    document_number: Optional[str]
    entity_gstin: Optional[str]
    entity_registration_no: Optional[str]

    # ── Validation ──
    validation_status: Optional[str]
    validation_reason: Optional[str]
    missing_fields: Optional[list]

    # ── Fraud / Authenticity (legacy-compatible names) ──
    requires_manual_review: bool
    authenticity_metadata_json: Optional[dict[str, Any]]   # maps from authenticity_metadata
    fraud_signal_weight: Optional[float]
    rejection_reason: Optional[str]

    # ── Timestamps ──
    created_at: datetime

    @field_validator("document_type", mode="before")
    @classmethod
    def _fill_document_type(cls, v: Any, info: Any) -> Any:
        """Allow document_type to be populated from document_type_code."""
        return v  # source is set by alias below

    @classmethod
    def model_validate(cls, obj: Any, **kwargs):  # type: ignore[override]
        """Override to copy document_type_code → document_type and
        authenticity_metadata → authenticity_metadata_json."""
        if hasattr(obj, "__tablename__"):
            # SQLAlchemy ORM model — convert to dict and patch alias fields
            from sqlalchemy import inspect as sa_inspect
            mapper = sa_inspect(type(obj))
            data: dict[str, Any] = {
                col.key: getattr(obj, col.key, None)
                for col in mapper.column_attrs
            }
            data["document_type"] = data.get("document_type_code")
            data["authenticity_metadata_json"] = data.pop("authenticity_metadata", None)
            return super().model_validate(data, **kwargs)
        return super().model_validate(obj, **kwargs)


class ClaimDocumentListResponse(BaseModel):
    items: list[ClaimDocumentResponse]
    total: int
