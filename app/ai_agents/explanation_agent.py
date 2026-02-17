"""
Explanation Generator Agent (backward-compatibility wrapper)

Delegates narrative generation to ``layer3_narrative`` in the new
fraud engine.  Preserves the original class name and method signatures.
"""
from typing import Dict, Any, List

from app.ai_agents.fraud import config as cfg


class ExplanationAgent:
    """
    Explanation generator

    CRITICAL: Produces human-readable explanations
    Required for regulatory compliance
    """

    def generate_explanation(
        self,
        fraud_score: float,
        rule_flags: List[str],
        anomaly_flags: List[str],
        behavior_flags: List[str],
        claim_context: Dict[str, Any],
    ) -> str:
        """
        Generate human-readable fraud explanation.

        Args:
            fraud_score: Overall fraud score
            rule_flags: Deterministic flags
            anomaly_flags: Statistical flags
            behavior_flags: Behavioral flags
            claim_context: Claim data

        Returns:
            Human-readable explanation string
        """
        claim_amount = claim_context.get("claim_amount", 0)
        claim_type = claim_context.get("claim_type", "")
        policy_number = claim_context.get("policy_number", "")

        explanation_parts = []

        # Header
        explanation_parts.append(
            f"Fraud Analysis for claim amount ₹{claim_amount:,.2f} "
            f"under policy {policy_number} ({claim_type})."
        )

        # Risk level from config boundaries
        risk_level = "MINIMAL"
        for level, boundary in cfg.RISK_LEVEL_BOUNDARIES.items():
            if fraud_score >= boundary:
                risk_level = level
                break

        explanation_parts.append(
            f"\n\nOverall Fraud Risk: {risk_level} (Score: {fraud_score:.2f})"
        )

        # Deterministic signals
        if rule_flags:
            explanation_parts.append("\n\nRule-Based Flags:")
            for flag in rule_flags:
                explanation_parts.append(f"  • {self._humanize_flag(flag)}")

        # Statistical signals
        if anomaly_flags:
            explanation_parts.append("\n\nStatistical Anomalies:")
            for flag in anomaly_flags:
                explanation_parts.append(f"  • {self._humanize_flag(flag)}")

        # Behavioral signals
        if behavior_flags:
            explanation_parts.append("\n\nBehavioral Patterns:")
            for flag in behavior_flags:
                explanation_parts.append(f"  • {self._humanize_flag(flag)}")

        # Recommendation
        explanation_parts.append("\n\nRecommendation:")
        if fraud_score >= cfg.RISK_LEVEL_BOUNDARIES["HIGH"]:
            explanation_parts.append(
                "  This claim requires MANUAL REVIEW by an insurance adjuster "
                "before approval due to elevated fraud risk indicators."
            )
        elif fraud_score >= cfg.RISK_LEVEL_BOUNDARIES["MODERATE"]:
            explanation_parts.append(
                "  Consider additional verification steps before proceeding with approval."
            )
        else:
            explanation_parts.append(
                "  Fraud risk is within acceptable parameters. Standard processing may proceed."
            )

        return "\n".join(explanation_parts)

    def _humanize_flag(self, flag: str) -> str:
        """
        Convert flag code to human-readable text.

        Args:
            flag: Flag code

        Returns:
            Human-readable description
        """
        flag_descriptions = {
            "AMOUNT_EXCEEDS_THRESHOLD": "Claim amount exceeds typical threshold for this claim type",
            "SUSPICIOUSLY_ROUND_AMOUNT": "Claim amount is a suspiciously round number",
            "INVALID_POLICY_FORMAT": "Policy number format appears invalid",
            "AMOUNT_STATISTICAL_OUTLIER": "Claim amount is a statistical outlier (>2.5 standard deviations)",
            "HIGH_RISK_PROVIDER_PATTERN": "Provider has exhibited high-risk patterns in historical data",
            "TEMPORAL_CLUSTERING_DETECTED": "Multiple claims detected in short time window",
            "UNUSUALLY_HIGH_CLAIM_FREQUENCY": "User has unusually high claim frequency",
            "CLAIM_AFTER_LONG_DORMANCY": "First claim after extended period of policy inactivity",
            "CLAIM_NEAR_POLICY_EXPIRY": "Claim submitted close to policy expiration date",
            "PREVIOUS_FRAUD_FLAGS_ON_RECORD": "User has previous fraud flags in historical records",
        }

        return flag_descriptions.get(flag, flag.replace("_", " ").title())