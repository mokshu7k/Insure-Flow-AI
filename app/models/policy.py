"""Policy ORM model.

A Policy represents an insurance policy held by a user, linked to a
specific insurer and PolicyType.  All the data that came from the
insurer at purchase time lives here (or in related PolicyDocument /
KYCDocument rows).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, _utcnow


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Ownership ──
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    insurer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurers.id"), nullable=True
    )
    policy_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policy_types.id"), nullable=True
    )

    # ── Core identifiers ──
    policy_number: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False
    )
    policy_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # denormalized from PolicyType.category for quick access

    status: Mapped[str] = mapped_column(
        String(32), default="ACTIVE", nullable=False
    )  # ACTIVE | EXPIRED | CANCELLED | LAPSED | PENDING_ACTIVATION

    # ── Financial ──
    sum_insured: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    premium_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    deductible: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    copay_percentage: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # ── Validity window ──
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # ── Insured person details (from policy purchase) ──
    insured_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    insured_dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    nominee_name: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # ── Coverage details ──
    # JSON blob describing exactly what's covered, limits, sub-limits, etc.
    coverage_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Policy schedule ──
    # Structured data extracted from or representing the policy schedule document
    policy_schedule: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Terms & Conditions ──
    terms_conditions_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    terms_conditions_ref: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # URL or storage path to T&C document

    # ── First premium receipt ──
    first_premium_receipt_ref: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # URL or storage path

    # ── Type-specific data ──
    # For VEHICLE: {"rc_number": "...", "vehicle_make": "...", ...}
    # For HEALTH: {"pre_existing_conditions": [...], "hospital_network": "...", ...}
    type_specific_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── General metadata ──
    meta_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Relationships ──
    user = relationship("User", back_populates="policies")
    insurer = relationship("Insurer", back_populates="policies")
    policy_type_ref = relationship("PolicyType", back_populates="policies")
    nominees = relationship(
        "PolicyNominee", back_populates="policy",
        cascade="all, delete-orphan", lazy="selectin",
    )
    policy_documents = relationship(
        "PolicyDocument", back_populates="policy",
        cascade="all, delete-orphan", lazy="selectin",
    )
    claims = relationship("Claim", back_populates="policy", lazy="selectin")

    __table_args__ = (
        Index("ix_policies_user_id", "user_id"),
        Index("ix_policies_insurer_id", "insurer_id"),
        Index("ix_policies_policy_type_id", "policy_type_id"),
        Index("ix_policies_policy_number", "policy_number"),
        Index("ix_policies_status", "status"),
        Index("ix_policies_policy_type", "policy_type"),
    )
