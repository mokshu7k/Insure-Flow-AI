"""
Dashboard schemas (Pydantic v2)
"""
from __future__ import annotations
from pydantic import BaseModel
from typing import Dict, Any, Optional


class OverviewMetrics(BaseModel):
    total_claims: int
    recent_claims_30d: int
    pending_manual_review: int
    total_settled_amount: float
    average_fraud_score: float
    status_breakdown: Dict[str, int]
    generated_at: str


class FraudDistribution(BaseModel):
    buckets: Dict[str, int]
    total_assessed: int
    high_risk_count: int
    mean_score: float
    generated_at: str


class SLAMetrics(BaseModel):
    average_days_to_decision: Optional[float]
    by_type: Dict[str, float]
    claims_analyzed: int
    generated_at: str


class ComplianceSummary(BaseModel):
    claims_with_fraud_analysis: int
    high_risk_claims: int
    human_review_required_count: int
    fraud_score_overrides: int
    compliance_rate: float
    generated_at: str