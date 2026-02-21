"""DocumentRequirement ORM model — defines what documents are needed
for a claim of a given policy type.

Each row says: "for policy type X, document type Y is
compulsory/optional, and here is the extraction template the LLM
should use when OCR-ing this document."
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentRequirement(Base):
    __tablename__ = "document_requirements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    policy_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policy_types.id"), nullable=False
    )

    # Document type code — matches DocumentType constants or custom codes
    document_type_code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)

    is_compulsory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Extraction template ──
    # JSON schema describing the fields the LLM must extract, e.g.:
    # {
    #   "fields": [
    #     {"key": "aadhaar_number", "type": "string", "required": true},
    #     {"key": "full_name", "type": "string", "required": true},
    #     {"key": "date_of_birth", "type": "date", "required": true},
    #     {"key": "address", "type": "string", "required": false}
    #   ],
    #   "instructions": "Extract the 12-digit Aadhaar number, full name as printed, ..."
    # }
    extraction_template: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Validation rules ──
    # JSON config for rule-based checks AFTER extraction, e.g.:
    # {
    #   "rules": [
    #     {"field": "aadhaar_number", "check": "regex", "pattern": "^\\d{12}$"},
    #     {"field": "date_of_birth", "check": "date_not_future"},
    #     {"field": "amount", "check": "range", "min": 0, "max": 10000000}
    #   ]
    # }
    validation_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Instructions shown to the user when uploading
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Allowed MIME types (e.g. ["image/jpeg","image/png","application/pdf"])
    allowed_mime_types: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    max_file_size_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships ──
    policy_type = relationship("PolicyType", back_populates="document_requirements")

    __table_args__ = (
        Index("ix_doc_req_policy_type_id", "policy_type_id"),
        Index(
            "uq_doc_req_type_doc",
            "policy_type_id", "document_type_code",
            unique=True,
        ),
    )
