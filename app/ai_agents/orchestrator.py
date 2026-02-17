"""
Fraud Orchestrator
Coordinates multi-agent fraud analysis
"""
from typing import Dict, Any

from app.schemas.fraud import FraudAnalysisResult
from app.ai_agents.rule_agent import RuleAgent
from app.ai_agents.anomaly_agent import AnomalyAgent
from app.ai_agents.behavior_agent import BehaviorAgent
from app.ai_agents.explanation_agent import ExplanationAgent


class FraudOrchestrator:
    """
    Multi-agent fraud analysis orchestrator
    
    ARCHITECTURE:
    1. Rule-based validator (deterministic)
    2. Statistical anomaly detector
    3. Behavioral pattern analyzer
    4. Explanation generator (human-readable)
    
    CRITICAL: Results are EXPLAINABLE for compliance
    """
    
    def __init__(self):
        self.rule_agent = RuleAgent()
        self.anomaly_agent = AnomalyAgent()
        self.behavior_agent = BehaviorAgent()
        self.explanation_agent = ExplanationAgent()
    
    def analyze(self, claim_context: Dict[str, Any]) -> FraudAnalysisResult:
        """
        Run multi-agent fraud analysis
        
        Args:
            claim_context: Claim data dictionary
        
        Returns:
            FraudAnalysisResult with score, flags, and explanation
        """
        # AGENT 1: Rule-based validation
        rule_flags = self.rule_agent.validate(claim_context)
        rule_score = len(rule_flags) * 0.15  # Each flag adds 15%
        
        # AGENT 2: Statistical anomaly detection
        anomaly_flags, anomaly_score = self.anomaly_agent.detect_anomalies(claim_context)
        
        # AGENT 3: Behavioral pattern analysis
        behavior_flags, behavior_score = self.behavior_agent.analyze_behavior(claim_context)
        
        # AGGREGATE SCORES (weighted)
        fraud_score = min(
            (rule_score * 0.4) + (anomaly_score * 0.35) + (behavior_score * 0.25),
            1.0  # Cap at 1.0
        )
        
        # AGENT 4: Generate human-readable explanation
        explanation = self.explanation_agent.generate_explanation(
            fraud_score=fraud_score,
            rule_flags=rule_flags,
            anomaly_flags=anomaly_flags,
            behavior_flags=behavior_flags,
            claim_context=claim_context
        )
        
        return FraudAnalysisResult(
            fraud_score=round(fraud_score, 3),
            deterministic_flags=rule_flags,
            statistical_flags=anomaly_flags,
            behavioral_flags=behavior_flags,
            explanation=explanation,
            metadata={
                "rule_score": round(rule_score, 3),
                "anomaly_score": round(anomaly_score, 3),
                "behavior_score": round(behavior_score, 3),
            }
        )