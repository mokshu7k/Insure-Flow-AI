"""
Layer 5 — Network / Provider Analysis
Checks provider claim frequency, cost patterns, and cluster relationships.
"""
from __future__ import annotations

from typing import Any


def run(context: dict[str, Any]) -> dict[str, Any]:
    flags: list[str] = []
    score = 0.0

    provider_id = context.get("provider_id")
    provider_claim_count_30d = int(context.get("provider_claim_count_30d", 0))
    provider_avg_claim_amount = float(context.get("provider_avg_claim_amount", 0))
    provider_fraud_flag_pct = float(context.get("provider_fraud_flag_pct", 0.0))
    claim_amount = float(context.get("claim_amount", 0))
    provider_cluster_risk = context.get("provider_cluster_risk", "LOW")

    if not provider_id:
        return {"score": 0.0, "flags": [], "layer": "network"}

    # Check 1: Provider submitting very high volume of claims
    if provider_claim_count_30d > 200:
        flags.append(f"HIGH_PROVIDER_VOLUME:{provider_claim_count_30d}")
        score = max(score, 0.45)

    # Check 2: This claim is way above provider's average
    if provider_avg_claim_amount > 0:
        multiplier = claim_amount / provider_avg_claim_amount
        if multiplier > 3.0:
            flags.append(f"CLAIM_3X_PROVIDER_AVERAGE:{multiplier:.1f}x")
            score = max(score, 0.60)

    # Check 3: Provider has historically high fraud flag rate
    if provider_fraud_flag_pct > 0.30:
        flags.append(f"PROVIDER_HIGH_FRAUD_RATE:{provider_fraud_flag_pct:.0%}")
        score = max(score, 0.70)
    elif provider_fraud_flag_pct > 0.15:
        flags.append(f"PROVIDER_ELEVATED_FRAUD_RATE:{provider_fraud_flag_pct:.0%}")
        score = max(score, 0.40)

    # Check 4: Provider is part of a known high-risk cluster
    if provider_cluster_risk == "HIGH":
        flags.append("PROVIDER_IN_HIGH_RISK_CLUSTER")
        score = max(score, 0.55)

    return {"score": min(score, 1.0), "flags": flags, "layer": "network"}
