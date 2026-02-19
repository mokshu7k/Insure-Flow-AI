"""
Fraud Engine Orchestrator
Coordinates all six detection layers, aggregator, and audit logger.
Contains NO business logic – pure coordination only.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict

from app.ai_agents.fraud import (
    aggregator,
    audit_logger,
    config as cfg,
    layer1_deterministic,
    layer2_statistical,
    layer3_narrative,
    layer4_document,
    layer5_network,
    layer6_ml,
)
from app.ai_agents.fraud.metrics import (
    FRAUD_AI_DEGRADED_TOTAL,
    FRAUD_CIRCUIT_BREAKER_OPEN_TOTAL,
    FRAUD_ENGINE_ANALYSIS_TOTAL,
    FRAUD_HIGH_RISK_TOTAL,
    FRAUD_LAYER_LATENCY,
    FRAUD_ML_UNAVAILABLE_TOTAL,
    FRAUD_SCORE_HISTOGRAM,
)
from app.schemas.fraud import FraudEngineResponse

logger = logging.getLogger(__name__)

# Behavioral flag → score contribution mapping (P0 fix: don't re-use l2.score)
_BEHAVIORAL_FLAG_SCORES: Dict[str, float] = {
    "UNUSUALLY_HIGH_CLAIM_FREQUENCY": cfg.FREQUENCY_RISK_SCORE,
    "PREVIOUS_FRAUD_FLAGS_ON_RECORD":  cfg.PRIOR_FRAUD_RISK_SCORE,
    "CLAIM_NEAR_POLICY_EXPIRY":        cfg.NEAR_EXPIRY_RISK_SCORE,
    "CLAIM_AFTER_LONG_DORMANCY":       cfg.DORMANCY_RISK_SCORE,
}


def _compute_risk_level(score: float) -> str:
    """Map a numeric fraud score to a human-readable risk level."""
    for label, threshold in sorted(
        cfg.RISK_LEVEL_BOUNDARIES.items(), key=lambda kv: kv[1], reverse=True
    ):
        if score >= threshold:
            return label
    return "MINIMAL"


class FraudEngineOrchestrator:
    """
    Production fraud-analysis orchestrator.

    Execution order:
        1. Layer 1 – Deterministic rules
        2. Layer 2 – Statistical anomalies
        3. Layer 3 – AI narrative (privacy-gated, circuit-breaker protected)
        4. Layer 4 – Document fraud detection
        5. Layer 5 – Network / provider graph analysis
        6. Layer 6 – Isolation Forest ML anomaly score
        7. Aggregation  (with degraded-mode weight renormalisation)
        8. Audit logging
        9. Return frozen FraudEngineResponse
    """

    def analyze(
        self,
        claim_context: Dict[str, Any],
        privacy_mode: str | None = None,
    ) -> FraudEngineResponse:
        """
        Run the full fraud-analysis pipeline.

        Args:
            claim_context: Pre-fetched claim data dict.  Required keys:
                ``claim_id``, ``claim_amount``, ``claim_type``,
                ``policy_number``.  Optional but enriching:
                ``recent_claim_count``, ``prior_fraud_flags``,
                ``days_to_policy_expiry``, ``last_claim_date``,
                ``total_claim_amount_90d``, ``provider_id``,
                ``provider_claim_count_30d``, ``provider_high_risk_count_30d``,
                ``provider_total_claims``, ``documents``,
                ``all_invoice_numbers``, ``claim_date``.
            privacy_mode: Override the privacy sanitiser mode
                (``"strict"`` | ``"balanced"`` | ``"raw"``).

        Returns:
            Frozen :class:`FraudEngineResponse` with ``config_version`` embedded.
        """
        claim_id = str(claim_context.get("claim_id", "unknown"))
        claim_type = str(claim_context.get("claim_type", "UNKNOWN"))
        effective_privacy = privacy_mode or cfg.DEFAULT_PRIVACY_MODE

        # Count every analysis
        FRAUD_ENGINE_ANALYSIS_TOTAL.labels(claim_type=claim_type).inc()

        # ------------------------------------------------------------------ #
        # Layer 1: Deterministic rules                                        #
        # ------------------------------------------------------------------ #
        _t0 = time.perf_counter()
        l1 = layer1_deterministic.evaluate(claim_context)
        FRAUD_LAYER_LATENCY.labels(layer="deterministic").observe(time.perf_counter() - _t0)

        # ------------------------------------------------------------------ #
        # Layer 2: Statistical anomalies                                      #
        # ------------------------------------------------------------------ #
        _t0 = time.perf_counter()
        l2 = layer2_statistical.evaluate(claim_context)
        FRAUD_LAYER_LATENCY.labels(layer="statistical").observe(time.perf_counter() - _t0)

        # Extract the behavioural subset for both the narrative layer and the
        # dedicated behavior_score metric (P0 fix: don't re-use l2.score).
        _behavioral_subset = [
            f for f in l2.anomalies
            if f in _BEHAVIORAL_FLAG_SCORES
        ]
        behavior_score = min(
            1.0,
            sum(_BEHAVIORAL_FLAG_SCORES.get(f, 0.0) for f in _behavioral_subset),
        )

        # ------------------------------------------------------------------ #
        # Layer 3: Narrative / AI  (circuit-breaker protected)               #
        # ------------------------------------------------------------------ #
        preliminary_score = (l1.score + l2.score) / 2.0
        _t0 = time.perf_counter()
        l3 = layer3_narrative.evaluate(
            claim_context=claim_context,
            deterministic_signals=l1.signals,
            statistical_anomalies=l2.anomalies,
            behavioral_flags=_behavioral_subset,
            preliminary_score=preliminary_score,
            privacy_mode=effective_privacy,
        )
        FRAUD_LAYER_LATENCY.labels(layer="narrative").observe(time.perf_counter() - _t0)
        if l3.ai_degraded_mode:
            FRAUD_AI_DEGRADED_TOTAL.inc()
        # Circuit-breaker events are logged inside layer3; also bump metric
        # when AI was forced into degraded mode (proxy for breaker open)
        if l3.ai_degraded_mode and not cfg.ENABLE_EXTERNAL_AI:
            pass  # AI disabled globally – not a circuit-breaker trip
        elif l3.ai_degraded_mode:
            FRAUD_CIRCUIT_BREAKER_OPEN_TOTAL.inc()

        # ------------------------------------------------------------------ #
        # Layer 4: Document fraud detection                                   #
        # ------------------------------------------------------------------ #
        _t0 = time.perf_counter()
        l4 = layer4_document.evaluate(claim_context)
        FRAUD_LAYER_LATENCY.labels(layer="document").observe(time.perf_counter() - _t0)

        # ------------------------------------------------------------------ #
        # Layer 5: Network / provider graph analysis                          #
        # ------------------------------------------------------------------ #
        _t0 = time.perf_counter()
        l5 = layer5_network.evaluate(claim_context)
        FRAUD_LAYER_LATENCY.labels(layer="network").observe(time.perf_counter() - _t0)

        # ------------------------------------------------------------------ #
        # Layer 6: Isolation Forest ML anomaly score                          #
        # ------------------------------------------------------------------ #
        _t0 = time.perf_counter()
        l6 = layer6_ml.evaluate(claim_context)
        FRAUD_LAYER_LATENCY.labels(layer="ml").observe(time.perf_counter() - _t0)
        if not l6.ml_available:
            FRAUD_ML_UNAVAILABLE_TOTAL.inc()

        # ------------------------------------------------------------------ #
        # Aggregation                                                         #
        # ------------------------------------------------------------------ #
        _t0 = time.perf_counter()
        agg = aggregator.aggregate(
            deterministic=l1,
            statistical=l2,
            narrative=l3,
            document=l4,
            network=l5,
            ml=l6,
        )
        FRAUD_LAYER_LATENCY.labels(layer="aggregation").observe(time.perf_counter() - _t0)

        risk_level = _compute_risk_level(agg.final_score)

        # Prometheus score + high-risk recording
        FRAUD_SCORE_HISTOGRAM.labels(claim_type=claim_type).observe(agg.final_score)
        if risk_level in ("HIGH", "VERY_HIGH"):
            FRAUD_HIGH_RISK_TOTAL.labels(claim_type=claim_type).inc()

        # ------------------------------------------------------------------ #
        # Build human-readable explanation from structured reasoning          #
        # ------------------------------------------------------------------ #
        reasoning = l3.structured_reasoning
        explanation_parts = [
            f"Fraud Analysis – Risk: {risk_level} "
            f"(Score: {agg.final_score:.2f})",
        ]
        summary = reasoning.get("summary", "")
        if summary:
            explanation_parts.append(f"\n\n{summary}")

        signals_explained = reasoning.get("signals_explained", {})
        if signals_explained:
            explanation_parts.append("\n\nSignals:")
            for _flag, desc in signals_explained.items():
                explanation_parts.append(f"  • {desc}")

        recommendation = reasoning.get("recommendation", "")
        if recommendation:
            explanation_parts.append(f"\n\nRecommendation:\n  {recommendation}")

        if l4.flags:
            explanation_parts.append("\n\nDocument Signals:")
            for f in l4.flags:
                explanation_parts.append(f"  • {f}")

        if l5.flags:
            explanation_parts.append("\n\nNetwork Signals:")
            for f in l5.flags:
                explanation_parts.append(f"  • {f}")

        explanation_text = "\n".join(explanation_parts)

        # ------------------------------------------------------------------ #
        # Metadata                                                            #
        # ------------------------------------------------------------------ #
        metadata: Dict[str, Any] = {
            "rule_score":      round(l1.score, 4),
            "anomaly_score":   round(l2.score, 4),
            # P0 fix: behavior_score is now computed from behavioral flags only
            "behavior_score":  round(behavior_score, 4),
            "narrative_score": round(l3.score, 4),
            "document_score":  round(l4.score, 4),
            "network_score":   round(l5.score, 4),
            "ml_score":        round(l6.score, 4),
            "agent_scores": {
                "rule_score":      round(l1.score, 4),
                "anomaly_score":   round(l2.score, 4),
                "behavior_score":  round(behavior_score, 4),
                "narrative_score": round(l3.score, 4),
                "document_score":  round(l4.score, 4),
                "network_score":   round(l5.score, 4),
                "ml_score":        round(l6.score, 4),
            },
            "risk_level":        risk_level,
            "ai_degraded_mode":  agg.ai_degraded_mode,
            "ml_model_used":     l6.ml_available,
            "config_version":    agg.config_version,
            "baseline_version":  agg.baseline_version,
        }

        # ------------------------------------------------------------------ #
        # Audit log                                                           #
        # ------------------------------------------------------------------ #
        audit_logger.log_assessment(
            claim_id=claim_id,
            final_score=agg.final_score,
            privacy_mode=effective_privacy,
            external_ai_used=cfg.ENABLE_EXTERNAL_AI and not l3.ai_degraded_mode,
            ai_degraded_mode=agg.ai_degraded_mode,
            config_version=agg.config_version,
            baseline_version=agg.baseline_version,
        )

        return FraudEngineResponse(
            fraud_score=round(agg.final_score, 3),
            deterministic_signals=list(l1.signals),
            statistical_anomalies=list(l2.anomalies),
            behavioral_flags=_behavioral_subset,
            document_flags=list(l4.flags),
            network_flags=list(l5.flags),
            structured_reasoning=dict(l3.structured_reasoning),
            explanation=explanation_text,
            risk_level=risk_level,
            config_version=agg.config_version,
            baseline_version=agg.baseline_version,
            ai_degraded_mode=agg.ai_degraded_mode,
            ml_model_used=l6.ml_available,
            metadata=metadata,
        )
