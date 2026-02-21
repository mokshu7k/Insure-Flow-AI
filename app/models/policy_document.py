"""PolicyDocument ORM model — documents collected at policy purchase time.

These come from the insurer side and represent the "ground truth" for
verification during claims.  They are NOT claim-submitted docs.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )

    # Matches DocumentType constants
    document_type_code: Mapped[str] = mapped_column(String(64), nullable=False)

    # Storage
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Pre-verified / pre-extracted data from insurer side
    extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Relationships ──
    policy = relationship("Policy", back_populates="policy_documents")

    __table_args__ = (
        Index("ix_policy_docs_policy_id", "policy_id"),
        Index("ix_policy_docs_type", "document_type_code"),
    )
