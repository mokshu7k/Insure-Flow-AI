"""ClaimStatusHistory ORM model — append-only log of every status
transition a claim goes through.

Provides a complete audit trail of who changed the status and why.
"""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ClaimStatusHistory(Base):
    __tablename__ = "claim_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False
    )

    from_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # null for initial creation
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)

    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )  # null for system-automated transitions

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ──
    claim = relationship("Claim", back_populates="status_history")
    changed_by_user = relationship("User", foreign_keys=[changed_by])

    __table_args__ = (
        Index("ix_claim_status_history_claim_id", "claim_id"),
        Index("ix_claim_status_history_created_at", "created_at"),
    )
