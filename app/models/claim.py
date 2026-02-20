"""Claim ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _utcnow


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    policy_number: Mapped[str] = mapped_column(String(128), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)
    claim_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="SUBMITTED", nullable=False)
    fraud_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    verified_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


    __table_args__ = (
        Index("ix_claims_user_id", "user_id"),
        Index("ix_claims_status", "status"),
        Index("ix_claims_created_at", "created_at"),
    )
