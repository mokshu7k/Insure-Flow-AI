"""
Aggregator
Combines weighted layer scores into a single fraud score.
Handles AI/ML degraded mode with weight renormalisation.
No magic numbers – all weights from config.py.
"""
from __future__ import annotations

import logging

from app.ai_agents.fraud import config as cfg
from app.schemas.fraud import (
    AggregatedScore,
    DeterministicResult,
    DocumentResult,
    MLResult,
    NarrativeResult,
    NetworkResult,
    StatisticalResult,
)

logger = logging.getLogger(__name__)


def aggregate(
    deterministic: DeterministicResult,
    statistical: StatisticalResult,
    narrative: NarrativeResult,
    document: DocumentResult,
    network: NetworkResult,
    ml: MLResult,
) -> AggregatedScore:
    """
    Produce a clamped, weighted fraud score from all six layers.

    Degraded-mode behaviour:
    - When ``narrative.ai_degraded_mode`` is True the narrative weight drops
      to zero and the remaining weights are renormalised so they still sum to 1.
    - When ``ml.ml_available`` is False the ML weight drops to zero similarly.

    Args:
        deterministic: Layer 1 result.
        statistical:   Layer 2 result.
        narrative:     Layer 3 result.
        document:      Layer 4 result.
        network:       Layer 5 result.
        ml:            Layer 6 result.

    Returns:
        AggregatedScore with clamped final_score in [0.0, 1.0].
    """
    ai_degraded = narrative.ai_degraded_mode
    ml_available = ml.ml_available

    if ai_degraded:
        # Narrative weight falls to L1/L2/L4
        w_det  = cfg.DEGRADED_WEIGHT_DETERMINISTIC
        w_stat = cfg.DEGRADED_WEIGHT_STATISTICAL
        w_narr = 0.0
        w_doc  = cfg.DEGRADED_WEIGHT_DOCUMENT
        w_net  = 0.0  # also drop network in degraded mode
        w_ml   = 0.0
    else:
        w_det  = cfg.WEIGHT_DETERMINISTIC
        w_stat = cfg.WEIGHT_STATISTICAL
        w_narr = cfg.WEIGHT_NARRATIVE
        w_doc  = cfg.WEIGHT_DOCUMENT
        w_net  = cfg.WEIGHT_NETWORK
        w_ml   = cfg.WEIGHT_ML if ml_available else 0.0

    total_weight = w_det + w_stat + w_narr + w_doc + w_net + w_ml

    if total_weight == 0.0:
        logger.error("All aggregation weights are zero – returning 0.0")
        raw_score = 0.0
    else:
        raw_score = (
            deterministic.score * w_det
            + statistical.score * w_stat
            + narrative.score * w_narr
            + document.score * w_doc
            + network.score * w_net
            + ml.score * w_ml
        ) / total_weight

    final_score = min(1.0, max(0.0, raw_score))

    layer_scores = {
        "deterministic": round(deterministic.score, 4),
        "statistical":   round(statistical.score, 4),
        "narrative":     round(narrative.score, 4),
        "document":      round(document.score, 4),
        "network":       round(network.score, 4),
        "ml":            round(ml.score, 4),
    }

    logger.debug(
        "Aggregator: degraded=%s ml_avail=%s weights=(%.2f,%.2f,%.2f,%.2f,%.2f,%.2f) "
        "layer_scores=%s final=%.4f",
        ai_degraded, ml_available,
        w_det, w_stat, w_narr, w_doc, w_net, w_ml,
        layer_scores, final_score,
    )

    return AggregatedScore(
        final_score=round(final_score, 4),
        layer_scores=layer_scores,
        config_version=cfg.CONFIG_VERSION,
        baseline_version=cfg.BASELINE_VERSION,
        ai_degraded_mode=ai_degraded,
    )


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
