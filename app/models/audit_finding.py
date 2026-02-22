"""AuditRun and AuditFinding ORM models — append-only, never update or delete.

AuditRun     : One row per scheduled auditor sweep.
AuditFinding : One row per suspicious pattern detected within a sweep.

Both tables are permanent evidence records.  No service should ever call
UPDATE or DELETE on these tables.  New suspicions always create new rows.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditRun(Base):
    """One complete auditor-agent sweep.  Append-only."""

    __tablename__ = "audit_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # e.g. "audit-2026-02-22T02:00:00"
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # RUNNING | COMPLETED | COMPLETED_WITH_ERRORS | FAILED
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RUNNING")

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    total_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    medium_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Gemini-generated executive summary for the entire sweep
    summary_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Any tool/DB errors encountered during the run
    errors: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    findings: Mapped[list["AuditFinding"]] = relationship(
        "AuditFinding", back_populates="audit_run", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_audit_runs_status", "status"),
        Index("ix_audit_runs_started_at", "started_at"),
    )


class AuditFinding(Base):
    """A single suspicious pattern found during one audit sweep.  Append-only.

    Finding types
    -------------
    ADJUSTER_PROVIDER_COLLUSION   — adjuster approves one provider at anomalous rate
    PROVIDER_OVERBILLING          — provider average claim spike >2.5x baseline in 30d
    UNDERPAYMENT_PATTERN          — adjuster systematically cuts approved vs claimed
    HIGH_FRAUD_SCORE_APPROVED     — fraud_score >0.70 on an APPROVED/SETTLED claim
    ABNORMAL_SETTLEMENT_SPEED     — SUBMITTED to SETTLED in <24 hours
    SETTLEMENT_AMOUNT_DISCREPANCY — settlement.amount differs from claim.approved_amount by >5%
    CLAIM_AMOUNT_GAP              — >40% cut with no documented adjuster reason
    PROVIDER_CLUSTER_ACTIVITY     — 3+ providers filing identical procedures in 7 days
    USER_CLAIM_SURGE              — user recent_claims_30d >4 with no fraud flag raised
    DOCUMENT_INTEGRITY_FLAGS      — repeated re-submissions / low confidence / FAIL results
    """

    __tablename__ = "audit_findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    audit_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ── Classification ────────────────────────────────────────────────────────
    finding_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # CRITICAL | HIGH | MEDIUM | LOW
    severity: Mapped[str] = mapped_column(String(16), nullable=False)

    # ── Entity references (plain strings — NOT FK so findings survive deletions) ──
    # CLAIM | PROVIDER | ADJUSTER | USER | CLUSTER
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # Primary suspect UUID or identifier
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # list[str] of related UUIDs
    supporting_entity_ids: Mapped[list] = mapped_column(
        JSONB, default=list, nullable=False
    )

    # ── Narrative ─────────────────────────────────────────────────────────────
    description: Mapped[str] = mapped_column(Text, nullable=False)
    gemini_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Raw evidence snapshot ─────────────────────────────────────────────────
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    audit_run: Mapped["AuditRun"] = relationship(
        "AuditRun", back_populates="findings"
    )

    __table_args__ = (
        Index("ix_audit_findings_run_id", "audit_run_id"),
        Index("ix_audit_findings_severity", "severity"),
        Index("ix_audit_findings_entity", "entity_type", "entity_id"),
        Index("ix_audit_findings_type", "finding_type"),
        Index("ix_audit_findings_created_at", "created_at"),
    )
