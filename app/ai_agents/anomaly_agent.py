"""
Anomaly Detection Agent
Statistical fraud detection
"""
from typing import Dict, Any, List, Tuple
import random


class AnomalyAgent:
    """
    Statistical anomaly detector
    
    APPROACH: Statistical analysis
    - Amount distribution analysis
    - Provider pattern detection
    - Temporal clustering
    
    In production: Would use real ML models
    """
    
    def __init__(self):
        # In production: Load trained models here
        # For now: Simulated statistical thresholds
        self.health_mean = 50000
        self.health_std = 25000
        self.motor_mean = 30000
        self.motor_std = 15000
    
    def detect_anomalies(self, claim_context: Dict[str, Any]) -> Tuple[List[str], float]:
        """
        Detect statistical anomalies
        
        Args:
            claim_context: Claim data
        
        Returns:
            Tuple of (flags, anomaly_score)
        """
        flags = []
        anomaly_score = 0.0
        
        claim_amount = claim_context.get("claim_amount", 0)
        claim_type = claim_context.get("claim_type", "")
        
        # ANOMALY 1: Amount deviation from mean
        if claim_type == "HEALTH":
            z_score = abs((claim_amount - self.health_mean) / self.health_std)
            if z_score > 2.5:  # More than 2.5 standard deviations
                flags.append("AMOUNT_STATISTICAL_OUTLIER")
                anomaly_score += 0.3
        
        elif claim_type == "MOTOR":
            z_score = abs((claim_amount - self.motor_mean) / self.motor_std)
            if z_score > 2.5:
                flags.append("AMOUNT_STATISTICAL_OUTLIER")
                anomaly_score += 0.3
        
        # ANOMALY 2: Provider frequency pattern
        # In production: Check if provider has unusual claim frequency
        # Simulated for demo
        provider_risk = random.choice([0.0, 0.0, 0.0, 0.2, 0.4])  # Mostly low risk
        if provider_risk > 0.3:
            flags.append("HIGH_RISK_PROVIDER_PATTERN")
            anomaly_score += provider_risk
        
        # ANOMALY 3: Time-based clustering
        # In production: Detect multiple claims in short time window
        # Simulated for demo
        time_risk = random.choice([0.0, 0.0, 0.0, 0.15])
        if time_risk > 0.1:
            flags.append("TEMPORAL_CLUSTERING_DETECTED")
            anomaly_score += time_risk
        
        return flags, min(anomaly_score, 1.0)