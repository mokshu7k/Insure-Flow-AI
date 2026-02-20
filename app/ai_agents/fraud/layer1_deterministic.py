"""
Layer 1 — Deterministic Rules
Hard checks that produce a binary FLAG or PASS result.
Score: sum(flags) / max_possible, capped at 1.0.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def run(context: dict[str, Any]) -> dict[str, Any]:
    flags: list[str] = []
    amount = float(context.get("claim_amount", 0))
    claim_type = context.get("claim_type", "")
    policy_number = context.get("policy_number", "")
    recent_claims = int(context.get("recent_claims_30d", 0))
    days_since_policy = int(context.get("days_since_policy_start", 999))
    blacklisted_providers = set(context.get("blacklisted_provider_ids", []))
    provider_id = context.get("provider_id")

    # Rule 1: Claim filed immediately after policy start
    if days_since_policy < 14:
        flags.append("CLAIM_FILED_<14D_AFTER_POLICY_START")

    # Rule 2: Unusually high amount for claim type
    limits = {"HEALTH": 500_000, "MOTOR": 300_000, "REIMBURSEMENT": 200_000, "CASHLESS": 150_000}
    if amount > limits.get(claim_type, 100_000):
        flags.append("AMOUNT_EXCEEDS_TYPE_LIMIT")

    # Rule 3: Excessive claim frequency
    if recent_claims >= 5:
        flags.append("HIGH_CLAIM_FREQUENCY_30D")
    elif recent_claims >= 3:
        flags.append("ELEVATED_CLAIM_FREQUENCY_30D")

    # Rule 4: Blacklisted provider
    if provider_id and provider_id in blacklisted_providers:
        flags.append("BLACKLISTED_PROVIDER")

    # Rule 5: Round-number amount (common in fabricated claims)
    if amount > 10_000 and amount % 1000 == 0:
        flags.append("ROUND_NUMBER_AMOUNT")

    score = min(len(flags) / 4.0, 1.0)
    return {"score": score, "flags": flags, "layer": "deterministic"}
