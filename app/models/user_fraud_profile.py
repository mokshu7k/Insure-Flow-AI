"""UserFraudProfile ORM model — rolling per-user fraud statistics."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserFraudProfile(Base):
    __tablename__ = "user_fraud_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)

    total_claims: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recent_claims_30d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_claim_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_claim_amount_90d: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    fraud_flag_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
