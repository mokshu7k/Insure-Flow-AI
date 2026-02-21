"""Claim ORM model.

Tracks the full claim lifecycle from draft through settlement.
Claims now have richer document ingestion states (DRAFT → DOCS_PENDING
→ DOCS_UNDER_VALIDATION → SUBMITTED → …) so we never process a claim
with incomplete/invalid documents.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, _utcnow


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Actor links ──
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Identifiers ──
    claim_number: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )  # auto-generated, human-readable
    policy_number: Mapped[str] = mapped_column(String(128), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # ── Financial ──
    claim_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    approved_amount: Mapped[float | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )

    # ── Incident details ──
    incident_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    situation_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Free-form JSON the user provides about their situation

    # ── Status & Workflow ──
    status: Mapped[str] = mapped_column(
        String(32), default="DRAFT", nullable=False
    )

    # ── Fraud / AI ──
    fraud_score: Mapped[float | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    adjuster_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_report: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Document completeness tracking ──
    total_docs_required: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_docs_submitted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_docs_validated: Mapped[int | None] = mapped_column(Integer, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )

    # ── Relationships ──
    user = relationship(
        "User", back_populates="claims", foreign_keys=[user_id]
    )
    provider = relationship("User", foreign_keys=[provider_id])
    policy = relationship("Policy", back_populates="claims")
    claim_documents = relationship(
        "ClaimDocument", back_populates="claim",
        lazy="selectin",
    )
    status_history = relationship(
        "ClaimStatusHistory", back_populates="claim",
        lazy="selectin", order_by="ClaimStatusHistory.created_at",
    )
    fraud_assessment = relationship(
        "FraudAssessment", uselist=False, lazy="selectin",
    )
    settlement = relationship(
        "Settlement", uselist=False, lazy="selectin",
    )

    __table_args__ = (
        Index("ix_claims_user_id", "user_id"),
        Index("ix_claims_provider_id", "provider_id"),
        Index("ix_claims_policy_id", "policy_id"),
        Index("ix_claims_claim_number", "claim_number"),
        Index("ix_claims_status", "status"),
        Index("ix_claims_created_at", "created_at"),
    )
