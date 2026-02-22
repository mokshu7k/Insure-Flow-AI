"""
Behavioral & Statistical Risk Analyzer — deterministic fraud signals.

Analyses claim-level metadata (timing, amounts, patterns) to detect
behavioural fraud indicators.  No LLM, no external API.

Signals checked:
  1. Claim timing  — days since policy activation
  2. Claim frequency — 30-day window
  3. Claim-to-sum-insured ratio
  4. 90-day aggregate claim total
  5. Prior fraud flag history
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────

_VERY_EARLY_CLAIM_DAYS = 30     # ≤ 30 days after policy start
_EARLY_CLAIM_DAYS      = 90     # ≤ 90 days

_HIGH_FREQUENCY_30D     = 3     # ≥ 3 claims in 30 days
_MODERATE_FREQUENCY_30D = 2

_HIGH_RATIO     = 0.80          # claiming 80 %+ of sum insured
_MODERATE_RATIO = 0.60

_VERY_HIGH_AGGREGATE_90D = 0.80 # 80 % of sum insured claimed in 90 days
_HIGH_AGGREGATE_90D      = 0.50

# Per-signal risk weights (0-100)
RISK_WEIGHTS: dict[str, int] = {
    "claim_before_policy":       95,
    "very_early_claim":          85,
    "early_claim":               45,
    "high_claim_frequency":      75,
    "moderate_claim_frequency":  35,
    "high_claim_ratio":          65,
    "moderate_claim_ratio":      30,
    "prior_fraud_flags":         70,
    "very_high_aggregate_90d":   80,
    "high_aggregate_90d":        60,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date(v: Any) -> date | None:
    """Best-effort date parser for common formats."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# ── Main analyser ─────────────────────────────────────────────────────────────

def analyze_behavioral_risk(claim_metadata: dict[str, Any]) -> dict[str, Any]:
    """Run all behavioural / statistical checks on *claim_metadata*.

    Parameters
    ----------
    claim_metadata : dict
        Keys used (all optional — missing → skip):
            claim_amount, claim_type, sum_insured,
            policy_start_date, claim_created_at,
            recent_claims_30d, total_claim_amount_90d,
            fraud_flag_count.

    Returns
    -------
    dict  with ``checks``, ``flags``, ``risk_score``.
    """
    if not claim_metadata:
        return {
            "checks": {"skipped": True, "reason": "No claim metadata provided"},
            "flags": ["SKIPPED: no claim metadata available"],
            "risk_score": 0.0,
        }

    flags: list[str] = []
    penalties: list[float] = []
    checks: dict[str, Any] = {}

    # ── 1. Claim timing (days since policy start) ────────────────────────────
    policy_start = _parse_date(claim_metadata.get("policy_start_date"))
    claim_date   = _parse_date(claim_metadata.get("claim_created_at"))

    if policy_start and claim_date:
        days = (claim_date - policy_start).days
        checks["days_since_policy_start"] = days

        if days < 0:
            flags.append(
                f"CLAIM_BEFORE_POLICY: claim filed {abs(days)} day(s) "
                "BEFORE policy start — policy may not have been active"
            )
            penalties.append(RISK_WEIGHTS["claim_before_policy"])
        elif days <= _VERY_EARLY_CLAIM_DAYS:
            flags.append(
                f"VERY_EARLY_CLAIM: claim filed only {days} day(s) "
                "after policy activation — high-risk early-claim pattern"
            )
            penalties.append(RISK_WEIGHTS["very_early_claim"])
        elif days <= _EARLY_CLAIM_DAYS:
            flags.append(
                f"EARLY_CLAIM: claim filed {days} day(s) after policy "
                "activation — moderately early"
            )
            penalties.append(RISK_WEIGHTS["early_claim"])
    else:
        checks["timing_analysis"] = "skipped — missing policy_start or claim date"

    # ── 2. Claim frequency ───────────────────────────────────────────────────
    recent = claim_metadata.get("recent_claims_30d", 0)
    checks["recent_claims_30d"] = recent

    if recent >= _HIGH_FREQUENCY_30D:
        flags.append(
            f"HIGH_CLAIM_FREQUENCY: {recent} claims filed in last 30 days "
            "— possible serial-claim pattern"
        )
        penalties.append(RISK_WEIGHTS["high_claim_frequency"])
    elif recent >= _MODERATE_FREQUENCY_30D:
        flags.append(
            f"MODERATE_CLAIM_FREQUENCY: {recent} claims in 30 days"
        )
        penalties.append(RISK_WEIGHTS["moderate_claim_frequency"])

    # ── 3. Claim-to-sum-insured ratio ────────────────────────────────────────
    claim_amount = claim_metadata.get("claim_amount")
    sum_insured  = claim_metadata.get("sum_insured")

    if claim_amount and sum_insured and float(sum_insured) > 0:
        ratio = float(claim_amount) / float(sum_insured)
        checks["claim_to_sum_insured_ratio"] = round(ratio, 4)

        if ratio > _HIGH_RATIO:
            flags.append(
                f"HIGH_CLAIM_RATIO: claim (₹{float(claim_amount):,.0f}) is "
                f"{ratio * 100:.0f}% of sum insured (₹{float(sum_insured):,.0f})"
            )
            penalties.append(RISK_WEIGHTS["high_claim_ratio"])
        elif ratio > _MODERATE_RATIO:
            flags.append(
                f"MODERATE_CLAIM_RATIO: claim is {ratio * 100:.0f}% of sum insured"
            )
            penalties.append(RISK_WEIGHTS["moderate_claim_ratio"])

    # ── 4. 90-day aggregate claims ───────────────────────────────────────────
    total_90d = claim_metadata.get("total_claim_amount_90d", 0)

    if total_90d and sum_insured and float(sum_insured) > 0:
        agg = float(total_90d) / float(sum_insured)
        checks["aggregate_90d_ratio"] = round(agg, 4)

        if agg > _VERY_HIGH_AGGREGATE_90D:
            flags.append(
                f"VERY_HIGH_AGGREGATE_CLAIMS: ₹{float(total_90d):,.0f} claimed in "
                f"90 days ({agg * 100:.0f}% of sum insured ₹{float(sum_insured):,.0f})"
            )
            penalties.append(RISK_WEIGHTS["very_high_aggregate_90d"])
        elif agg > _HIGH_AGGREGATE_90D:
            flags.append(
                f"HIGH_AGGREGATE_CLAIMS: ₹{float(total_90d):,.0f} claimed in "
                f"90 days ({agg * 100:.0f}% of sum insured)"
            )
            penalties.append(RISK_WEIGHTS["high_aggregate_90d"])

    # ── 5. Prior fraud flags ─────────────────────────────────────────────────
    fraud_count = claim_metadata.get("fraud_flag_count", 0)
    checks["prior_fraud_flags"] = fraud_count

    if fraud_count > 0:
        flags.append(
            f"PRIOR_FRAUD_HISTORY: {fraud_count} previous fraud "
            f"flag{'s' if fraud_count > 1 else ''} on this policyholder"
        )
        penalties.append(RISK_WEIGHTS["prior_fraud_flags"])

    # ── Score (max-dominant with diminishing tail) ───────────────────────────
    if not penalties:
        risk_score = 0.0
    else:
        max_p = max(penalties)
        others = sum(p for p in penalties if p != max_p)
        risk_score = min(100.0, max_p + min(25.0, others * 0.2))

    return {
        "checks": checks,
        "flags": flags,
        "risk_score": round(risk_score, 1),
    }
