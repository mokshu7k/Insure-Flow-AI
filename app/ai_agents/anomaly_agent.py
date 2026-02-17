"""
Anomaly Detection Agent (backward-compatibility wrapper)

Delegates to ``layer2_statistical`` in the new fraud engine.
Preserves the original class name and ``detect_anomalies()`` method.

The old implementation used ``random.choice()`` – the new engine is
fully deterministic, reading ``recent_claim_count``, ``prior_fraud_flags``,
and ``days_to_policy_expiry`` from the claim context instead.
"""
from typing import Dict, Any, List, Tuple

from app.ai_agents.fraud import layer2_statistical
from app.ai_agents.fraud import config as cfg


class AnomalyAgent:
    """
    Statistical anomaly detector

    APPROACH: Statistical analysis
    - Amount distribution analysis
    - Provider pattern detection
    - Temporal clustering
    """

    def __init__(self) -> None:
        # Expose baselines for backward compatibility
        self.health_mean = cfg.STATISTICAL_BASELINES["HEALTH"]["mean"]
        self.health_std = cfg.STATISTICAL_BASELINES["HEALTH"]["std"]
        self.motor_mean = cfg.STATISTICAL_BASELINES["MOTOR"]["mean"]
        self.motor_std = cfg.STATISTICAL_BASELINES["MOTOR"]["std"]

    def detect_anomalies(self, claim_context: Dict[str, Any]) -> Tuple[List[str], float]:
        """
        Detect statistical anomalies.

        Args:
            claim_context: Claim data

        Returns:
            Tuple of (flags, anomaly_score)
        """
        result = layer2_statistical.evaluate(claim_context)
        # Filter to only anomaly-type flags (exclude behavioral for this method)
        anomaly_flags = [
            f for f in result.anomalies
            if f in {
                "AMOUNT_STATISTICAL_OUTLIER",
                "HIGH_RISK_PROVIDER_PATTERN",
                "TEMPORAL_CLUSTERING_DETECTED",
            }
        ]
        return anomaly_flags, result.score