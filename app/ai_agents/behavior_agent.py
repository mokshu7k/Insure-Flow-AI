"""
Behavior Pattern Agent (backward-compatibility wrapper)

Delegates to ``layer2_statistical`` in the new fraud engine.
Preserves the original class name and ``analyze_behavior()`` method.

The old implementation used ``random.choice()`` – the new engine is
fully deterministic, reading ``recent_claim_count``, ``prior_fraud_flags``,
and ``days_to_policy_expiry`` from the claim context instead.
"""
from typing import Dict, Any, List, Tuple

from app.ai_agents.fraud import layer2_statistical


class BehaviorAgent:
    """
    Behavioral pattern analyzer

    APPROACH: User behavior analysis
    - Claim frequency patterns
    - Policy utilization rates
    - Historical red flags
    """

    def analyze_behavior(self, claim_context: Dict[str, Any]) -> Tuple[List[str], float]:
        """
        Analyze user behavioral patterns.

        Args:
            claim_context: Claim data with user_id

        Returns:
            Tuple of (flags, behavior_score)
        """
        result = layer2_statistical.evaluate(claim_context)
        # Filter to only behavioral flags
        behavioral_flags = [
            f for f in result.anomalies
            if f in {
                "UNUSUALLY_HIGH_CLAIM_FREQUENCY",
                "CLAIM_AFTER_LONG_DORMANCY",
                "CLAIM_NEAR_POLICY_EXPIRY",
                "PREVIOUS_FRAUD_FLAGS_ON_RECORD",
            }
        ]

        # Compute a proportional behavior-only score
        behavior_score = 0.0
        for flag in behavioral_flags:
            if flag == "UNUSUALLY_HIGH_CLAIM_FREQUENCY":
                behavior_score += 0.35
            elif flag == "PREVIOUS_FRAUD_FLAGS_ON_RECORD":
                behavior_score += 0.40
            elif flag == "CLAIM_NEAR_POLICY_EXPIRY":
                behavior_score += 0.20
            elif flag == "CLAIM_AFTER_LONG_DORMANCY":
                behavior_score += 0.15

        return behavioral_flags, min(1.0, behavior_score)