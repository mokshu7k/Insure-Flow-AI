"""
Layer 2 – Statistical Anomaly Detector
Operates on pre-fetched historical data. No DB queries, no AI calls.
Deterministic seeding for reproducibility.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.ai_agents.fraud import config as cfg
from app.ai_agents.fraud.schemas import StatisticalResult

logger = logging.getLogger(__name__)


def evaluate(
    claim_context: Dict[str, Any],
) -> StatisticalResult:
    """
    Detect statistical anomalies in a claim.

    All historical data (``recent_claim_count``, ``prior_fraud_flags``,
    ``days_to_policy_expiry``) must be **pre-fetched** and provided in
    ``claim_context`` by the caller – this layer never touches the DB.

    Args:
        claim_context: Claim data dict enriched with historical fields.

    Returns:
        StatisticalResult with normalised score in [0.0, 1.0] and anomaly list.
    """
    anomalies: list[str] = []
    raw_score: float = 0.0

    claim_amount: float = claim_context.get("claim_amount", 0.0)
    claim_type: str = claim_context.get("claim_type", "")

    # ----- Amount z-score analysis -----
    baseline = cfg.STATISTICAL_BASELINES.get(claim_type)
    if baseline is not None:
        mean = baseline["mean"]
        std = baseline["std"]
        if std > 0:
            z_score = abs((claim_amount - mean) / std)
            if z_score > cfg.Z_SCORE_THRESHOLD:
                anomalies.append("AMOUNT_STATISTICAL_OUTLIER")
                raw_score += cfg.Z_SCORE_ANOMALY_CONTRIBUTION

    # ----- Behavioral: claim frequency -----
    recent_claim_count: int = claim_context.get("recent_claim_count", 0)
    if recent_claim_count >= cfg.HIGH_CLAIM_FREQUENCY_THRESHOLD:
        anomalies.append("UNUSUALLY_HIGH_CLAIM_FREQUENCY")
        raw_score += cfg.FREQUENCY_RISK_SCORE

    # ----- Behavioral: prior fraud flags -----
    prior_fraud_flags: int = claim_context.get("prior_fraud_flags", 0)
    if prior_fraud_flags >= cfg.PRIOR_FRAUD_FLAGS_THRESHOLD:
        anomalies.append("PREVIOUS_FRAUD_FLAGS_ON_RECORD")
        raw_score += cfg.PRIOR_FRAUD_RISK_SCORE

    # ----- Behavioral: claim near policy expiry -----
    days_to_expiry = claim_context.get("days_to_policy_expiry")
    if days_to_expiry is not None and days_to_expiry <= cfg.DAYS_TO_EXPIRY_THRESHOLD:
        anomalies.append("CLAIM_NEAR_POLICY_EXPIRY")
        raw_score += cfg.NEAR_EXPIRY_RISK_SCORE

    # Normalise to [0, 1]
    score = min(1.0, max(0.0, raw_score))

    logger.debug(
        "Layer2 statistical: anomalies=%s score=%.3f",
        anomalies,
        score,
    )

    return StatisticalResult(score=score, anomalies=anomalies)
