"""Document ORM model — LEGACY compatibility layer.

The canonical claim-document model is now ``ClaimDocument`` (in
``claim_document.py``).  This file keeps the ``documents`` table alive
so that existing code referencing ``Document`` continues to work while
the migration to ClaimDocument is completed.

For new code, always import ``ClaimDocument`` instead.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    uploader_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)

    extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    requires_manual_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Document validation fields (from DocumentGatekeeper)
    validation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    validation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    authenticity_metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fraud_signal_weight: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)

    __table_args__ = (
        Index("ix_documents_claim_id", "claim_id"),
        Index("ix_documents_uploader_id", "uploader_id"),
    )
