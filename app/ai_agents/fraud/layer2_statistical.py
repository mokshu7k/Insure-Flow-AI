"""
Layer 2 — Statistical Anomaly Detection
Z-score analysis on claim amount and frequency relative to user history.
"""
from __future__ import annotations

import math
from typing import Any


def _zscore(value: float, mean: float, std: float) -> float:
    if std < 1e-9:
        return 0.0
    return (value - mean) / std


def _sigmoid(x: float) -> float:
    """Maps any z-score to [0, 1]. Positive scores indicate high anomaly."""
    return 1.0 / (1.0 + math.exp(-0.5 * x))


def run(context: dict[str, Any]) -> dict[str, Any]:
    signals: list[str] = []
    score = 0.0

    amount = float(context.get("claim_amount", 0))
    user_mean_amount = float(context.get("user_mean_claim_amount", amount))
    user_std_amount = float(context.get("user_std_claim_amount", 1.0))
    frequency = float(context.get("recent_claims_30d", 0))
    mean_frequency = float(context.get("population_mean_frequency", 1.0))
    std_frequency = float(context.get("population_std_frequency", 0.5))

    # Amount z-score
    amount_z = _zscore(amount, user_mean_amount, user_std_amount)
    if amount_z > 2.5:
        signals.append(f"AMOUNT_ZSCORE={amount_z:.2f}")
        score = max(score, _sigmoid(amount_z))
    elif amount_z > 1.5:
        signals.append(f"ELEVATED_AMOUNT_ZSCORE={amount_z:.2f}")
        score = max(score, _sigmoid(amount_z) * 0.6)

    # Frequency z-score
    freq_z = _zscore(frequency, mean_frequency, std_frequency)
    if freq_z > 2.0:
        signals.append(f"FREQUENCY_ZSCORE={freq_z:.2f}")
        score = max(score, _sigmoid(freq_z) * 0.8)

    # Rapid escalation in 90-day total
    amount_90d = float(context.get("total_claim_amount_90d", 0))
    if amount_90d > 1_000_000:
        signals.append("90D_TOTAL_EXCEEDS_1M")
        score = max(score, 0.7)

    return {"score": min(score, 1.0), "signals": signals, "layer": "statistical"}
