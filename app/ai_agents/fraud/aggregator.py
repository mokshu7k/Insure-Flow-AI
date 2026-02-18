"""
Aggregator
Combines weighted layer scores into a single fraud score.
Handles AI degraded mode with weight renormalisation.
No magic numbers – all weights from config.py.
"""
from __future__ import annotations

import logging

from app.ai_agents.fraud import config as cfg
from app.schemas.fraud import (
    AggregatedScore,
    DeterministicResult,
    NarrativeResult,
    StatisticalResult,
)

logger = logging.getLogger(__name__)


def aggregate(
    deterministic: DeterministicResult,
    statistical: StatisticalResult,
    narrative: NarrativeResult,
) -> AggregatedScore:
    """
    Produce a clamped, weighted fraud score.

    When ``narrative.ai_degraded_mode`` is True the narrative weight drops
    to zero and the remaining weights are renormalised so they still sum
    to 1.0.

    Args:
        deterministic: Layer 1 result (score already in [0, 1]).
        statistical: Layer 2 result (score already in [0, 1]).
        narrative: Layer 3 result (score already in [0, 1]).

    Returns:
        AggregatedScore with clamped final_score in [0.0, 1.0].
    """
    ai_degraded = narrative.ai_degraded_mode

    if ai_degraded:
        w_det = cfg.DEGRADED_WEIGHT_DETERMINISTIC
        w_stat = cfg.DEGRADED_WEIGHT_STATISTICAL
        w_narr = 0.0
    else:
        w_det = cfg.WEIGHT_DETERMINISTIC
        w_stat = cfg.WEIGHT_STATISTICAL
        w_narr = cfg.WEIGHT_NARRATIVE

    total_weight = w_det + w_stat + w_narr

    # Guard against misconfigured zero-sum weights
    if total_weight == 0.0:
        logger.error("All aggregation weights are zero – returning 0.0")
        raw_score = 0.0
    else:
        raw_score = (
            deterministic.score * w_det
            + statistical.score * w_stat
            + narrative.score * w_narr
        ) / total_weight

    # Enforce clamping
    final_score = min(1.0, max(0.0, raw_score))

    layer_scores = {
        "deterministic": round(deterministic.score, 4),
        "statistical": round(statistical.score, 4),
        "narrative": round(narrative.score, 4),
    }

    logger.debug(
        "Aggregator: degraded=%s weights=(%.2f, %.2f, %.2f) "
        "layer_scores=%s final=%.4f",
        ai_degraded,
        w_det,
        w_stat,
        w_narr,
        layer_scores,
        final_score,
    )

    return AggregatedScore(
        final_score=round(final_score, 4),
        layer_scores=layer_scores,
        config_version=cfg.CONFIG_VERSION,
        baseline_version=cfg.BASELINE_VERSION,
        ai_degraded_mode=ai_degraded,
    )
