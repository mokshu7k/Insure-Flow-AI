"""
Fraud score aggregator — weighted combination of all 6 layer scores.
Avoids duplicating metadata (the bug from the old version).
"""
from __future__ import annotations

from typing import Any

from app.ai_agents.fraud.config import cfg


def aggregate(layer_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    Compute final weighted score from per-layer results.
    Returns a clean dict — no duplicated keys between top-level and nested.
    """
    weights = cfg.LAYER_WEIGHTS
    final_score = 0.0
    layer_scores: dict[str, float] = {}
    all_flags: list[str] = []

    for layer_name, weight in weights.items():
        result = layer_results.get(layer_name, {})
        score = float(result.get("score", 0.0))
        layer_scores[layer_name] = score
        final_score += score * weight
        # Collect flags/signals (whatever key the layer uses)
        for flag_key in ("flags", "signals"):
            all_flags.extend(result.get(flag_key, []))

    final_score = min(final_score, 1.0)
    risk_level = _risk_level(final_score)

    return {
        "final_score": round(final_score, 4),
        "risk_level": risk_level,
        "layer_scores": layer_scores,  # flat, no duplication
        "all_flags": all_flags,
    }


def _risk_level(score: float) -> str:
    for label, threshold in sorted(
        cfg.RISK_LEVEL_BOUNDARIES.items(), key=lambda kv: kv[1], reverse=True
    ):
        if score >= threshold:
            return label
    return "MINIMAL"
