"""
AuditPersistenceService — the ONLY place audit_runs and audit_findings are written.

No UPDATE or DELETE paths exist anywhere in this service.
Every sweep creates new rows.  Evidence is stored verbatim for
reproducibility and legal defensibility.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AuditPersistenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_run(
        self,
        *,
        run_id: str,
        findings: list[dict[str, Any]],
        raw_signals: dict[str, Any],
        summary_narrative: str | None,
        errors: dict[str, str],
    ) -> None:
        """
        Persist one complete audit sweep atomically.

        Creates:
          1. One AuditRun row (summary of the sweep)
          2. One AuditFinding row per finding Gemini classified

        The transaction is committed once at the end — if anything fails,
        the entire sweep is rolled back so the DB never has a partial record.
        """
        from app.models.audit_finding import AuditRun, AuditFinding

        now = datetime.now(timezone.utc)

        # Count findings by severity
        counts: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for f in findings:
            sev = (f.get("severity") or "LOW").upper()
            if sev in counts:
                counts[sev] += 1

        status = "COMPLETED" if not errors else "COMPLETED_WITH_ERRORS"

        # ── AuditRun ──────────────────────────────────────────────────────────
        run = AuditRun(
            id=uuid.uuid4(),
            run_id=run_id,
            status=status,
            started_at=now,
            completed_at=now,
            total_findings=len(findings),
            critical_count=counts["CRITICAL"],
            high_count=counts["HIGH"],
            medium_count=counts["MEDIUM"],
            low_count=counts["LOW"],
            summary_narrative=summary_narrative,
            errors=errors or {},
        )
        self.db.add(run)
        await self.db.flush()  # get run.id before inserting findings

        # ── AuditFinding rows ─────────────────────────────────────────────────
        skipped = 0
        for f in findings:
            if not f.get("finding_type") or not f.get("entity_id"):
                logger.warning("[AuditPersistence] Skipping malformed finding: %s", f)
                skipped += 1
                continue

            # Attach relevant raw signal data as evidence
            signal_key = _finding_type_to_signal_key(f.get("finding_type", ""))
            evidence = f.get("evidence") or {}
            if not evidence and signal_key and signal_key in raw_signals:
                evidence = raw_signals[signal_key]

            finding = AuditFinding(
                id=uuid.uuid4(),
                audit_run_id=run.id,
                finding_type=f.get("finding_type", "UNKNOWN"),
                severity=(f.get("severity") or "LOW").upper(),
                entity_type=(f.get("entity_type") or "CLAIM").upper(),
                entity_id=str(f.get("entity_id", "")),
                supporting_entity_ids=f.get("supporting_entity_ids") or [],
                description=f.get("description") or "",
                gemini_narrative=f.get("gemini_narrative"),
                recommended_action=f.get("recommended_action"),
                evidence=evidence,
            )
            self.db.add(finding)

        await self.db.commit()
        logger.info(
            "[AuditPersistence] Saved run=%s status=%s findings=%d "
            "(CRITICAL=%d HIGH=%d MEDIUM=%d LOW=%d) skipped=%d",
            run_id, status, len(findings),
            counts["CRITICAL"], counts["HIGH"], counts["MEDIUM"], counts["LOW"],
            skipped,
        )


def _finding_type_to_signal_key(finding_type: str) -> str:
    """Map finding type enum value to the raw_signals dict key."""
    _MAP = {
        "ADJUSTER_PROVIDER_COLLUSION":   "adjuster_provider_collusion",
        "PROVIDER_OVERBILLING":          "provider_overbilling",
        "UNDERPAYMENT_PATTERN":          "underpayment_pattern",
        "HIGH_FRAUD_SCORE_APPROVED":     "high_fraud_score_approved",
        "ABNORMAL_SETTLEMENT_SPEED":     "abnormal_settlement_speed",
        "SETTLEMENT_AMOUNT_DISCREPANCY": "settlement_discrepancy",
        "CLAIM_AMOUNT_GAP":              "claim_amount_gap",
        "PROVIDER_CLUSTER_ACTIVITY":     "provider_cluster_activity",
        "USER_CLAIM_SURGE":              "user_claim_surge",
        "DOCUMENT_INTEGRITY_FLAGS":      "document_integrity",
    }
    return _MAP.get(finding_type.upper(), "")
