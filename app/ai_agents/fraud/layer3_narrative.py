"""
Layer 3 – Narrative / AI Explanation Generator
Routes through privacy.py before any processing.
Supports local-only mode (default) and external AI with timeout fallback.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.ai_agents.fraud import config as cfg
from app.ai_agents.fraud import privacy
from app.ai_agents.fraud.schemas import NarrativeResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Risk-level classifier (used by local narrative)
# ---------------------------------------------------------------------------
def _classify_risk(score: float) -> str:
    """Return a human-readable risk level string."""
    for level, boundary in cfg.RISK_LEVEL_BOUNDARIES.items():
        if score >= boundary:
            return level
    return "MINIMAL"


# ---------------------------------------------------------------------------
# Flag humaniser
# ---------------------------------------------------------------------------
_FLAG_DESCRIPTIONS: Dict[str, str] = {
    "AMOUNT_EXCEEDS_THRESHOLD": "Claim amount exceeds typical threshold for this claim type",
    "SUSPICIOUSLY_ROUND_AMOUNT": "Claim amount is a suspiciously round number",
    "INVALID_POLICY_FORMAT": "Policy number format appears invalid",
    "AMOUNT_STATISTICAL_OUTLIER": "Claim amount is a statistical outlier (>2.5 standard deviations)",
    "HIGH_RISK_PROVIDER_PATTERN": "Provider has exhibited high-risk patterns in historical data",
    "TEMPORAL_CLUSTERING_DETECTED": "Multiple claims detected in short time window",
    "UNUSUALLY_HIGH_CLAIM_FREQUENCY": "User has unusually high claim frequency",
    "CLAIM_AFTER_LONG_DORMANCY": "First claim after extended period of policy inactivity",
    "CLAIM_NEAR_POLICY_EXPIRY": "Claim submitted close to policy expiration date",
    "PREVIOUS_FRAUD_FLAGS_ON_RECORD": "User has previous fraud flags in historical records",
}


def _humanize_flag(flag: str) -> str:
    return _FLAG_DESCRIPTIONS.get(flag, flag.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Recommendation text
# ---------------------------------------------------------------------------
def _recommendation(fraud_score: float) -> str:
    if fraud_score >= cfg.RISK_LEVEL_BOUNDARIES["HIGH"]:
        return (
            "This claim requires MANUAL REVIEW by an insurance adjuster "
            "before approval due to elevated fraud risk indicators."
        )
    if fraud_score >= cfg.RISK_LEVEL_BOUNDARIES["MODERATE"]:
        return "Consider additional verification steps before proceeding with approval."
    return "Fraud risk is within acceptable parameters. Standard processing may proceed."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def evaluate(
    claim_context: Dict[str, Any],
    deterministic_signals: List[str],
    statistical_anomalies: List[str],
    behavioral_flags: List[str],
    preliminary_score: float,
    privacy_mode: str | None = None,
) -> NarrativeResult:
    """
    Generate a structured fraud narrative.

    1. Sanitises input through ``privacy.py``.
    2. Produces a structured-reasoning dict (no free text).
    3. Falls back to ``NARRATIVE_DEFAULT_SCORE`` on failure.

    Args:
        claim_context: Raw claim data.
        deterministic_signals: Flags from Layer 1.
        statistical_anomalies: Flags from Layer 2.
        behavioral_flags: Subset of statistical anomalies relating to behaviour.
        preliminary_score: Weighted score *before* narrative contribution.
        privacy_mode: Override privacy mode (default from config).

    Returns:
        NarrativeResult with score in [0.0, 1.0] and structured reasoning.
    """
    ai_degraded_mode = False

    # --- privacy gate ---
    sanitized_context = privacy.sanitize(claim_context, mode=privacy_mode)

    # --- Try external AI if enabled ---
    if cfg.ENABLE_EXTERNAL_AI:
        try:
            result = _call_external_ai(
                sanitized_context,
                deterministic_signals,
                statistical_anomalies,
                behavioral_flags,
                preliminary_score,
            )
            return result
        except Exception:
            logger.warning(
                "External AI call failed or timed out – "
                "falling back to local narrative. ai_degraded_mode=True"
            )
            ai_degraded_mode = True

    # --- Local-only narrative (default path) ---
    return _build_local_narrative(
        sanitized_context,
        deterministic_signals,
        statistical_anomalies,
        behavioral_flags,
        preliminary_score,
        ai_degraded_mode=ai_degraded_mode,
    )


# ---------------------------------------------------------------------------
# Local narrative builder
# ---------------------------------------------------------------------------
def _build_local_narrative(
    sanitized_context: Dict[str, Any],
    deterministic_signals: List[str],
    statistical_anomalies: List[str],
    behavioral_flags: List[str],
    preliminary_score: float,
    *,
    ai_degraded_mode: bool = False,
) -> NarrativeResult:
    """Build a fully structured narrative without any external calls."""
    risk_level = _classify_risk(preliminary_score)

    signals_explained: Dict[str, str] = {}
    for flag in deterministic_signals:
        signals_explained[flag] = _humanize_flag(flag)
    for flag in statistical_anomalies:
        signals_explained[flag] = _humanize_flag(flag)
    for flag in behavioral_flags:
        if flag not in signals_explained:
            signals_explained[flag] = _humanize_flag(flag)

    structured_reasoning: Dict[str, object] = {
        "risk_level": risk_level,
        "summary": (
            f"Fraud risk assessment: {risk_level} "
            f"(score: {preliminary_score:.2f}). "
            f"{len(signals_explained)} signal(s) identified."
        ),
        "signals_explained": signals_explained,
        "recommendation": _recommendation(preliminary_score),
    }

    # The narrative layer itself contributes a small score adjustment
    # based on signal density when running locally.
    total_signals = (
        len(deterministic_signals)
        + len(statistical_anomalies)
        + len(behavioral_flags)
    )
    local_score = min(1.0, total_signals * 0.10)

    return NarrativeResult(
        score=local_score,
        structured_reasoning=structured_reasoning,
        ai_degraded_mode=ai_degraded_mode,
    )


# ---------------------------------------------------------------------------
# External AI stub (guarded by ENABLE_EXTERNAL_AI)
# ---------------------------------------------------------------------------
def _call_external_ai(
    sanitized_context: Dict[str, Any],
    deterministic_signals: List[str],
    statistical_anomalies: List[str],
    behavioral_flags: List[str],
    preliminary_score: float,
) -> NarrativeResult:
    """
    Placeholder for external AI integration.

    In production this would call a controlled AI endpoint with
    ``cfg.AI_TIMEOUT_SECONDS`` as the request timeout.

    Raises:
        NotImplementedError: Always – external AI not yet wired.
    """
    raise NotImplementedError(
        "External AI integration is not yet implemented. "
        "Set ENABLE_EXTERNAL_AI = False to use local-only mode."
    )
