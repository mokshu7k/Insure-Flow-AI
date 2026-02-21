"""PolicyNominee ORM model — nominees linked to a policy."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PolicyNominee(Base):
    __tablename__ = "policy_nominees"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )

    full_name: Mapped[str] = mapped_column(String(256), nullable=False)
    relationship_to_insured: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SPOUSE, CHILD, PARENT, SIBLING, OTHER
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Percentage of the sum insured this nominee gets
    share_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2), default=100.0, nullable=False
    )

    # Extra contact / identification info
    contact_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g. {"phone": "...", "email": "...", "id_type": "PAN", "id_number": "..."}

    # ── Relationships ──
    policy = relationship("Policy", back_populates="nominees")

    __table_args__ = (
        Index("ix_policy_nominees_policy_id", "policy_id"),
    )
