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
    Returns a clean dict with proper structure for frontend display.
    """
    weights = cfg.LAYER_WEIGHTS
    final_score = 0.0
    layer_scores: dict[str, dict[str, Any]] = {}  # Changed to include full layer info
    all_flags: list[str] = []

    for layer_name, weight in weights.items():
        result = layer_results.get(layer_name, {})
        score = float(result.get("score", 0.0))
        
        # Collect flags/signals (whatever key the layer uses)
        flags = []
        for flag_key in ("flags", "signals"):
            flags.extend(result.get(flag_key, []))
        
        # Store complete layer info for frontend display
        layer_scores[layer_name] = {
            "score": score,
            "flags": flags,
            "layer": result.get("layer", layer_name),
            "method": result.get("method"),
            "ai_degraded": result.get("ai_degraded", False),
        }
        
        final_score += score * weight
        all_flags.extend(flags)

    final_score = min(final_score, 1.0)
    risk_level = _risk_level(final_score)

    return {
        "final_score": round(final_score, 4),
        "risk_level": risk_level,
        "layer_scores": layer_scores,  # Now includes full layer structure
        "all_flags": all_flags,
    }


def _risk_level(score: float) -> str:
    for label, threshold in sorted(
        cfg.RISK_LEVEL_BOUNDARIES.items(), key=lambda kv: kv[1], reverse=True
    ):
        if score >= threshold:
            return label
    return "MINIMAL"
