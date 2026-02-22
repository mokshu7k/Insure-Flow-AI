"""Add audit_runs and audit_findings tables (immutable auditor evidence store)

Revision ID: h0001_add_audit_findings
Revises: g0001_schema_overhaul
Create Date: 2026-02-22
"""
from __future__ import annotations

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "h0001_add_audit_findings"
down_revision: Union[str, None] = "g0001_schema_overhaul"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── audit_runs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.String(64), unique=True, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="RUNNING"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_findings", sa.Integer, nullable=False, server_default="0"),
        sa.Column("critical_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("high_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("medium_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("low_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("summary_narrative", sa.Text, nullable=True),
        sa.Column("errors", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_audit_runs_status", "audit_runs", ["status"])
    op.create_index("ix_audit_runs_started_at", "audit_runs", ["started_at"])
    op.execute(
        "COMMENT ON TABLE audit_runs IS "
        "'Immutable. Append-only. Do NOT UPDATE or DELETE rows.'"
    )

    # ── audit_findings ────────────────────────────────────────────────────────
    op.create_table(
        "audit_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audit_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("finding_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column(
            "supporting_entity_ids",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
        ),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("gemini_narrative", sa.Text, nullable=True),
        sa.Column("recommended_action", sa.Text, nullable=True),
        sa.Column(
            "evidence", postgresql.JSONB, nullable=False, server_default="{}"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_audit_findings_run_id", "audit_findings", ["audit_run_id"])
    op.create_index("ix_audit_findings_severity", "audit_findings", ["severity"])
    op.create_index(
        "ix_audit_findings_entity", "audit_findings", ["entity_type", "entity_id"]
    )
    op.create_index("ix_audit_findings_type", "audit_findings", ["finding_type"])
    op.create_index(
        "ix_audit_findings_created_at", "audit_findings", ["created_at"]
    )
    op.execute(
        "COMMENT ON TABLE audit_findings IS "
        "'Immutable. Append-only. Do NOT UPDATE or DELETE rows.'"
    )


def downgrade() -> None:
    op.drop_table("audit_findings")
    op.drop_table("audit_runs")
