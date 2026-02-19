"""
Layer 5 – Network / Graph Analysis
Detects ring fraud patterns through provider-level and cross-claim graph signals.

Checks
------
1. HIGH_RISK_PROVIDER      – provider has N+ claims in the window, with elevated
                              fraud rate above cfg.PROVIDER_FRAUD_RATE_THRESHOLD
2. PROVIDER_FRAUD_CLUSTER  – provider appears in a connected cluster of
                              high-score claims within the window

No DB calls – all data must be pre-fetched in claim_context by ClaimContextBuilder.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.ai_agents.fraud import config as cfg
from app.schemas.fraud import NetworkResult

logger = logging.getLogger(__name__)


def evaluate(claim_context: Dict[str, Any]) -> NetworkResult:
    """
    Detect network-level fraud patterns.

    Args:
        claim_context: Must include:
            - ``provider_id``                 (str | None)
            - ``provider_claim_count_30d``    (int)
            - ``provider_high_risk_count_30d`` (int) – claims with fraud_score >= 0.7
            - ``provider_total_claims``       (int)

    Returns:
        NetworkResult with normalised score in [0.0, 1.0] and flag list.
    """
    flags: List[str] = []
    raw_score: float = 0.0

    provider_id: str | None = claim_context.get("provider_id")

    # No provider associated with this claim – skip network analysis
    if not provider_id:
        return NetworkResult(score=0.0, flags=[])

    provider_claim_count_30d: int = int(
        claim_context.get("provider_claim_count_30d", 0)
    )
    provider_high_risk_count_30d: int = int(
        claim_context.get("provider_high_risk_count_30d", 0)
    )
    provider_total_claims: int = int(
        claim_context.get("provider_total_claims", 0)
    )

    # ── CHECK 1: Provider with high claim volume and elevated fraud rate ──
    if provider_claim_count_30d >= cfg.PROVIDER_HIGH_CLAIM_COUNT_THRESHOLD:
        fraud_rate = (
            provider_high_risk_count_30d / provider_claim_count_30d
            if provider_claim_count_30d > 0 else 0.0
        )
        if fraud_rate >= cfg.PROVIDER_FRAUD_RATE_THRESHOLD:
            flags.append("HIGH_RISK_PROVIDER")
            raw_score += cfg.HIGH_RISK_PROVIDER_SCORE
            logger.debug(
                "Layer5: HIGH_RISK_PROVIDER provider=%s fraud_rate=%.2f count_30d=%d",
                provider_id, fraud_rate, provider_claim_count_30d,
            )

    # ── CHECK 2: Provider appears in a fraud cluster ──────────────────────
    # If the provider has > THRESHOLD claims overall AND a high fraud rate,
    # they represent a fraud cluster regardless of time window.
    if (
        provider_total_claims >= cfg.PROVIDER_HIGH_CLAIM_COUNT_THRESHOLD * 2
        and "HIGH_RISK_PROVIDER" in flags
    ):
        flags.append("PROVIDER_FRAUD_CLUSTER")
        raw_score += cfg.SHARED_PROVIDER_CLUSTER_SCORE
        logger.debug(
            "Layer5: PROVIDER_FRAUD_CLUSTER provider=%s total_claims=%d",
            provider_id, provider_total_claims,
        )

    score = min(1.0, max(0.0, raw_score))
    logger.debug("Layer5 network: flags=%s score=%.3f", flags, score)

    return NetworkResult(score=score, flags=flags)
