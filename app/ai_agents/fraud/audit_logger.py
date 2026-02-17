"""
Audit Logger
Structured fraud-engine audit events.
Uses app.core.logging – never logs raw claim data.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.ai_agents.fraud import config as cfg

# Use the dedicated audit logger from the application logging infra.
# Falls back to a module-level logger if the audit logger is not yet set up.
try:
    from app.core.logging import get_audit_logger
    _audit_logger = get_audit_logger()
except Exception:
    _audit_logger = logging.getLogger("audit.fraud_engine")

logger = logging.getLogger(__name__)


def log_assessment(
    *,
    claim_id: str,
    final_score: float,
    privacy_mode: str,
    external_ai_used: bool,
    ai_degraded_mode: bool,
    config_version: str,
    baseline_version: str,
    extra: Dict[str, Any] | None = None,
) -> None:
    """
    Write an immutable fraud-assessment audit record.

    NEVER logs raw claim data – only operational metadata.

    Args:
        claim_id: Claim identifier (safe to log).
        final_score: Clamped fraud score [0.0, 1.0].
        privacy_mode: Privacy mode that was active.
        external_ai_used: Whether Layer 3 called an external AI endpoint.
        ai_degraded_mode: Whether the AI layer timed out / failed.
        config_version: Engine config version used.
        baseline_version: Statistical baseline version used.
        extra: Optional additional metadata (must not contain PII).
    """
    record: Dict[str, Any] = {
        "event": "FRAUD_ASSESSMENT",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "claim_id": claim_id,
        "final_score": round(final_score, 4),
        "privacy_mode": privacy_mode,
        "external_ai_used": external_ai_used,
        "ai_degraded_mode": ai_degraded_mode,
        "config_version": config_version,
        "baseline_version": baseline_version,
    }

    if extra:
        record["extra"] = extra

    _audit_logger.info(
        "fraud_assessment claim_id=%s score=%.4f privacy=%s "
        "external_ai=%s degraded=%s cfg=%s baseline=%s",
        claim_id,
        final_score,
        privacy_mode,
        external_ai_used,
        ai_degraded_mode,
        config_version,
        baseline_version,
    )

    logger.debug("Audit record emitted: %s", record)
