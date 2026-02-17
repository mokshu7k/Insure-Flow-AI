"""
Rule-Based Fraud Agent (backward-compatibility wrapper)

Delegates to ``layer1_deterministic`` in the new fraud engine.
Preserves the original class name and ``validate()`` method signature.
"""
from typing import Dict, Any, List

from app.ai_agents.fraud import layer1_deterministic


class RuleAgent:
    """
    Rule-based fraud validator

    APPROACH: Deterministic checks
    - Duplicate invoice detection
    - Amount threshold violations
    - Time-based anomalies
    - Policy validation
    """

    def validate(self, claim_context: Dict[str, Any]) -> List[str]:
        """
        Apply rule-based fraud checks.

        Args:
            claim_context: Claim data

        Returns:
            List of fraud flags
        """
        result = layer1_deterministic.evaluate(claim_context)
        return list(result.signals)