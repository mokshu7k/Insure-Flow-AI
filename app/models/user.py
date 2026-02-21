"""User ORM model.

Represents any actor in the system: policyholders (CUSTOMER),
hospitals/garages (PROVIDER), insurer staff (INSURER_ADMIN),
auditors, or automated system accounts.

Policyholders are linked to an insurer via `insurer_id` and identified
by the unique ID their insurer assigned them (`insurer_customer_id`).
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Insurer link (nullable for system admins / auditors) ──
    insurer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurers.id"), nullable=True
    )

    # The unique ID the insurer gave this customer (what they log in with)
    insurer_customer_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )

    # ── Auth ──
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Personal details (populated from insurer data sync) ──
    full_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g. {"line1": "...", "city": "...", "state": "...", "pincode": "..."}

    # ── Relationships ──
    insurer = relationship("Insurer", back_populates="users")
    kyc_documents = relationship("KYCDocument", back_populates="user", lazy="selectin")
    policies = relationship(
        "Policy", back_populates="user",
        foreign_keys="Policy.user_id", lazy="selectin",
    )
    claims = relationship(
        "Claim", back_populates="user",
        foreign_keys="Claim.user_id", lazy="selectin",
    )

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_insurer_id", "insurer_id"),
        Index(
            "uq_users_insurer_customer_id",
            "insurer_id", "insurer_customer_id",
            unique=True,
            postgresql_where="insurer_customer_id IS NOT NULL",
        ),
    )
