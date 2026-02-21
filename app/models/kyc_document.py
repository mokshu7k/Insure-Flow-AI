"""KYCDocument ORM model — identity / KYC data that arrived from the
insurer when the customer originally purchased the policy.

When the customer later files a claim and uploads (e.g.) their Aadhaar,
the OCR output is matched against this stored, insurer-verified data.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class KYCDocument(Base):
    __tablename__ = "kyc_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # e.g. AADHAAR, PAN, DRIVING_LICENSE, PASSPORT, VOTER_ID
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)

    # The core identifier (encrypted / hashed at rest in production)
    document_number: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Structured data that was verified by the insurer, e.g.:
    # {"full_name": "...", "dob": "...", "address": "...", "gender": "M"}
    document_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # When and how this was verified
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_source: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )  # e.g. "INSURER_SYNC", "DIGILOCKER", "MANUAL"

    # Soft-delete / supersede
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships ──
    user = relationship("User", back_populates="kyc_documents")

    __table_args__ = (
        Index("ix_kyc_user_id", "user_id"),
        Index("ix_kyc_doc_type", "document_type"),
        Index(
            "uq_kyc_user_doctype_active",
            "user_id", "document_type",
            unique=True,
            postgresql_where="is_active = true",
        ),
    )
