"""
Behavior Pattern Agent
User behavioral analysis
"""
from typing import Dict, Any, List, Tuple
import random


class BehaviorAgent:
    """
    Behavioral pattern analyzer
    
    APPROACH: User behavior analysis
    - Claim frequency patterns
    - Policy utilization rates
    - Historical red flags
    
    In production: Would use user history from DB
    """
    
    def analyze_behavior(self, claim_context: Dict[str, Any]) -> Tuple[List[str], float]:
        """
        Analyze user behavioral patterns
        
        Args:
            claim_context: Claim data with user_id
        
        Returns:
            Tuple of (flags, behavior_score)
        """
        flags = []
        behavior_score = 0.0
        
        # In production: Query user's claim history from DB
        # For now: Simulated behavioral analysis
        
        # BEHAVIOR 1: Unusual claim frequency
        # Simulate: Check if user has made multiple claims recently
        claim_frequency_risk = random.choice([0.0, 0.0, 0.0, 0.2, 0.35])
        if claim_frequency_risk > 0.3:
            flags.append("UNUSUALLY_HIGH_CLAIM_FREQUENCY")
            behavior_score += claim_frequency_risk
        
        # BEHAVIOR 2: First claim after long dormancy
        # Simulate: Check if policy was inactive for long period
        dormancy_risk = random.choice([0.0, 0.0, 0.0, 0.15])
        if dormancy_risk > 0.1:
            flags.append("CLAIM_AFTER_LONG_DORMANCY")
            behavior_score += dormancy_risk
        
        # BEHAVIOR 3: Policy near expiry
        # Simulate: Check if claim submitted close to policy expiry
        expiry_risk = random.choice([0.0, 0.0, 0.0, 0.2])
        if expiry_risk > 0.15:
            flags.append("CLAIM_NEAR_POLICY_EXPIRY")
            behavior_score += expiry_risk
        
        # BEHAVIOR 4: Historical fraud flags
        # Simulate: Check if user has previous fraud flags
        history_risk = random.choice([0.0, 0.0, 0.0, 0.0, 0.4])
        if history_risk > 0.3:
            flags.append("PREVIOUS_FRAUD_FLAGS_ON_RECORD")
            behavior_score += history_risk
        
        return flags, min(behavior_score, 1.0)