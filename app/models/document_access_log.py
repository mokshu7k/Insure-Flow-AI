"""DocumentAccessLog ORM model — per-document HIPAA-style access log."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentAccessLog(Base):
    __tablename__ = "document_access_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # VIEWED, DOWNLOADED, OCR_READ

    __table_args__ = (
        Index("ix_doc_access_document_id", "document_id"),
        Index("ix_doc_access_user_id", "user_id"),
    )
