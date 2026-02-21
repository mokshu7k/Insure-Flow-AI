"""Insurer ORM model — the insurance company (tenant)."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Insurer(Base):
    __tablename__ = "insurers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Display & identification
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    code: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )  # short unique slug, e.g. "HDFC_ERGO", "ICICI_LOMBARD"
    registration_number: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True
    )  # IRDAI registration or equivalent

    # Contact
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Integration config — API keys, webhook URLs, data-sync settings, etc.
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships (back-populates set on child side) ──
    users = relationship("User", back_populates="insurer", lazy="selectin")
    policy_types = relationship("PolicyType", back_populates="insurer", lazy="selectin")
    policies = relationship("Policy", back_populates="insurer", lazy="selectin")

    __table_args__ = (
        Index("ix_insurers_code", "code"),
        Index("ix_insurers_is_active", "is_active"),
    )
