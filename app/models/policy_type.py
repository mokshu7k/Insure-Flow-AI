"""PolicyType ORM model — configurable insurance verticals per insurer.

Each insurer can define their own policy types (Health Individual,
Health Family Floater, Motor Comprehensive, Motor Third-Party, …).
Adding a new type is a DB row, not a code change.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PolicyType(Base):
    __tablename__ = "policy_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    insurer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurers.id"), nullable=False
    )

    # e.g. "HEALTH", "MOTOR", "LIFE", ...
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    # More specific, e.g. "HEALTH_INDIVIDUAL", "MOTOR_COMPREHENSIVE"
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Insurer-specific config for this type
    # e.g. max_sum_insured, default_deductible, co-pay %, waiting periods …
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships ──
    insurer = relationship("Insurer", back_populates="policy_types")
    document_requirements = relationship(
        "DocumentRequirement", back_populates="policy_type", lazy="selectin"
    )
    policies = relationship("Policy", back_populates="policy_type_ref", lazy="selectin")

    __table_args__ = (
        Index("ix_policy_types_insurer_id", "insurer_id"),
        Index("ix_policy_types_category", "category"),
        Index("uq_policy_types_insurer_code", "insurer_id", "code", unique=True),
    )
