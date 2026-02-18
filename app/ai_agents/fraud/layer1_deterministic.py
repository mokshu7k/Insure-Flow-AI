"""
Layer 1 – Deterministic Rule Engine
Pure business-logic fraud rules. No DB, no external calls.
All thresholds sourced from config.py.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.ai_agents.fraud import config as cfg
from app.schemas.fraud import DeterministicResult

logger = logging.getLogger(__name__)


def evaluate(claim_context: Dict[str, Any]) -> DeterministicResult:
    """
    Apply deterministic business rules to a claim context.

    Args:
        claim_context: Pre-fetched claim data dict.

    Returns:
        DeterministicResult with normalised score in [0.0, 1.0] and signal list.
    """
    signals: list[str] = []

    claim_amount: float = claim_context.get("claim_amount", 0.0)
    claim_type: str = claim_context.get("claim_type", "")
    policy_number: str = claim_context.get("policy_number", "")

    # RULE 1: Amount exceeds type-specific threshold
    threshold = cfg.CLAIM_AMOUNT_THRESHOLDS.get(claim_type)
    if threshold is not None and claim_amount > threshold:
        signals.append("AMOUNT_EXCEEDS_THRESHOLD")

    # RULE 2: Suspiciously round amount
    if (
        cfg.ROUND_AMOUNT_MODULUS > 0
        and claim_amount > cfg.ROUND_AMOUNT_FLOOR
        and claim_amount % cfg.ROUND_AMOUNT_MODULUS == 0
    ):
        signals.append("SUSPICIOUSLY_ROUND_AMOUNT")

    # RULE 3: Policy number too short
    if len(policy_number) < cfg.MIN_POLICY_NUMBER_LENGTH:
        signals.append("INVALID_POLICY_FORMAT")

    # Score: each signal contributes SCORE_PER_DETERMINISTIC_SIGNAL, capped at 1.0
    raw_score = len(signals) * cfg.SCORE_PER_DETERMINISTIC_SIGNAL
    score = min(1.0, max(0.0, raw_score))

    logger.debug(
        "Layer1 deterministic: signals=%s score=%.3f",
        signals,
        score,
    )

    return DeterministicResult(score=score, signals=signals)
