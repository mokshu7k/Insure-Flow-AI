"""DocumentValidationResult ORM model — individual validation check
results for a claim document.

Each document goes through multiple validation stages (structural,
OCR quality, field completeness, KYC match, rule-based, authenticity).
Each stage produces one row here for a complete audit trail.
"""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentValidationResult(Base):
    __tablename__ = "document_validation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    claim_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claim_documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Which validation step — matches ValidationCheckType constants
    validation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # e.g. STRUCTURAL, OCR_QUALITY, FIELD_COMPLETENESS, KYC_MATCH, RULE_BASED, AUTHENTICITY

    # Outcome
    result: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # PASS, FAIL, WARNING

    # Human-readable summary
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Structured details (rule-specific output)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Relationships ──
    claim_document = relationship("ClaimDocument", back_populates="validation_results")

    __table_args__ = (
        Index("ix_val_results_doc_id", "claim_document_id"),
        Index("ix_val_results_type", "validation_type"),
    )
