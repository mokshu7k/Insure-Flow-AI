"""QRToken ORM model — HMAC cashless auth tokens."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QRToken(Base):
    __tablename__ = "qr_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    token_hash: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    approved_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Cashless-specific fields
    status: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)
    estimate_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    patient_name: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    procedure_name: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    hospital_name: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    insurer_notes: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    __table_args__ = (
        Index("ix_qr_tokens_token_hash", "token_hash"),
        Index("ix_qr_tokens_claim_id", "claim_id"),
        Index("ix_qr_tokens_provider_id", "provider_id"),
        Index("ix_qr_tokens_status", "status"),
    )
