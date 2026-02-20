"""FraudAssessment ORM model — one per claim (upsert on re-analysis)."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FraudAssessment(Base):
    __tablename__ = "fraud_assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"), unique=True, nullable=False)

    fraud_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)

    deterministic_signals: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    statistical_signals: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    behavioral_flags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    document_flags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    network_flags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    layer_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    layer_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    explanation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    config_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_degraded_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ml_model_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (Index("ix_fraud_assessments_claim_id", "claim_id"),)
