"""
Fraud Engine Orchestrator
Coordinates the three detection layers, aggregator, and audit logger.
Contains NO business logic – pure coordination only.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.ai_agents.fraud import (
    aggregator,
    audit_logger,
    config as cfg,
    layer1_deterministic,
    layer2_statistical,
    layer3_narrative,
)
from app.ai_agents.fraud.schemas import FraudAssessmentResponse

logger = logging.getLogger(__name__)


class FraudEngineOrchestrator:
    """
    Production fraud-analysis orchestrator.

    Execution order:
        1. Layer 1 – Deterministic rules
        2. Layer 2 – Statistical anomalies
        3. Layer 3 – AI narrative (privacy-gated)
        4. Aggregation (with degraded-mode handling)
        5. Audit logging
        6. Return frozen FraudAssessmentResponse
    """

    def analyze(
        self,
        claim_context: Dict[str, Any],
        privacy_mode: str | None = None,
    ) -> FraudAssessmentResponse:
        """
        Run the full fraud-analysis pipeline.

        Args:
            claim_context: Pre-fetched claim data dict (must contain
                ``claim_id``, ``claim_amount``, ``claim_type``,
                ``policy_number``, and optionally ``recent_claim_count``,
                ``prior_fraud_flags``, ``days_to_policy_expiry``).
            privacy_mode: Override for the privacy sanitiser mode.

        Returns:
            Frozen FraudAssessmentResponse with ``config_version`` embedded.
        """
        claim_id = str(claim_context.get("claim_id", "unknown"))
        effective_privacy = privacy_mode or cfg.DEFAULT_PRIVACY_MODE

        # ---- Layer 1: Deterministic ----
        l1 = layer1_deterministic.evaluate(claim_context)

        # ---- Layer 2: Statistical ----
        l2 = layer2_statistical.evaluate(claim_context)

        # Separate behavioural flags for the narrative layer
        _behavioral_subset = [
            f for f in l2.anomalies
            if f in {
                "UNUSUALLY_HIGH_CLAIM_FREQUENCY",
                "PREVIOUS_FRAUD_FLAGS_ON_RECORD",
                "CLAIM_NEAR_POLICY_EXPIRY",
                "CLAIM_AFTER_LONG_DORMANCY",
            }
        ]

        # Preliminary score for narrative context (unweighted average)
        preliminary_score = (l1.score + l2.score) / 2.0

        # ---- Layer 3: Narrative ----
        l3 = layer3_narrative.evaluate(
            claim_context=claim_context,
            deterministic_signals=l1.signals,
            statistical_anomalies=l2.anomalies,
            behavioral_flags=_behavioral_subset,
            preliminary_score=preliminary_score,
            privacy_mode=effective_privacy,
        )

        # ---- Aggregation ----
        agg = aggregator.aggregate(
            deterministic=l1,
            statistical=l2,
            narrative=l3,
        )

        # ---- Build explanation text from structured reasoning ----
        reasoning = l3.structured_reasoning
        explanation_parts = [
            f"Fraud Analysis – Risk: {reasoning.get('risk_level', 'UNKNOWN')} "
            f"(Score: {agg.final_score:.2f})",
        ]
        summary = reasoning.get("summary", "")
        if summary:
            explanation_parts.append(f"\n\n{summary}")

        signals_explained = reasoning.get("signals_explained", {})
        if signals_explained:
            explanation_parts.append("\n\nSignals:")
            for flag, desc in signals_explained.items():
                explanation_parts.append(f"  • {desc}")

        recommendation = reasoning.get("recommendation", "")
        if recommendation:
            explanation_parts.append(f"\n\nRecommendation:\n  {recommendation}")

        explanation_text = "\n".join(explanation_parts)

        # ---- Metadata ----
        metadata: Dict[str, Any] = {
            "rule_score": round(l1.score, 4),
            "anomaly_score": round(l2.score, 4),
            "behavior_score": round(l2.score, 4),
            "narrative_score": round(l3.score, 4),
            "agent_scores": {
                "rule_score": round(l1.score, 4),
                "anomaly_score": round(l2.score, 4),
                "behavior_score": round(l2.score, 4),
                "narrative_score": round(l3.score, 4),
            },
            "ai_degraded_mode": agg.ai_degraded_mode,
            "config_version": agg.config_version,
            "baseline_version": agg.baseline_version,
        }

        # ---- Audit ----
        audit_logger.log_assessment(
            claim_id=claim_id,
            final_score=agg.final_score,
            privacy_mode=effective_privacy,
            external_ai_used=cfg.ENABLE_EXTERNAL_AI and not l3.ai_degraded_mode,
            ai_degraded_mode=agg.ai_degraded_mode,
            config_version=agg.config_version,
            baseline_version=agg.baseline_version,
        )

        return FraudAssessmentResponse(
            fraud_score=round(agg.final_score, 3),
            deterministic_signals=list(l1.signals),
            statistical_anomalies=list(l2.anomalies),
            behavioral_flags=_behavioral_subset,
            structured_reasoning=dict(l3.structured_reasoning),
            explanation=explanation_text,
            config_version=agg.config_version,
            baseline_version=agg.baseline_version,
            ai_degraded_mode=agg.ai_degraded_mode,
            metadata=metadata,
        )
