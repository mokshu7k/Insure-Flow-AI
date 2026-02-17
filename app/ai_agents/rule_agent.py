"""
Rule-Based Fraud Agent
Deterministic fraud detection rules
"""
from typing import Dict, Any, List


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
        Apply rule-based fraud checks
        
        Args:
            claim_context: Claim data
        
        Returns:
            List of fraud flags
        """
        flags = []
        
        claim_amount = claim_context.get("claim_amount", 0)
        claim_type = claim_context.get("claim_type", "")
        
        # RULE 1: Unusually high claim amount
        if claim_type == "HEALTH":
            if claim_amount > 500000:  # 5 lakh
                flags.append("AMOUNT_EXCEEDS_THRESHOLD")
        elif claim_type == "MOTOR":
            if claim_amount > 200000:  # 2 lakh
                flags.append("AMOUNT_EXCEEDS_THRESHOLD")
        
        # RULE 2: Round number suspicion
        if claim_amount % 10000 == 0 and claim_amount > 50000:
            flags.append("SUSPICIOUSLY_ROUND_AMOUNT")
        
        # RULE 3: Multiple claims simulation (would check DB)
        # In production: check for duplicate invoices, rapid claims
        # For now, simulate with placeholder
        if claim_amount > 100000:
            # Placeholder: Would query DB for recent claims
            pass
        
        # RULE 4: Policy number format validation
        policy_number = claim_context.get("policy_number", "")
        if len(policy_number) < 8:
            flags.append("INVALID_POLICY_FORMAT")
        
        return flags