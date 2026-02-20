"""Dashboard schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Dict

from pydantic import BaseModel, Field


class ClaimsByStatus(BaseModel):
    SUBMITTED: int = 0
    UNDER_REVIEW: int = 0
    MANUAL_REVIEW_REQUIRED: int = 0
    APPROVED: int = 0
    REJECTED: int = 0
    SETTLED: int = 0


class DashboardOverview(BaseModel):
    total_claims: int
    recent_claims_30d: int = 0
    pending_manual_review: int = 0
    total_settled_amount: float = 0.0
    average_fraud_score: float
    high_risk_count: int
    status_breakdown: Dict[str, int] = Field(default_factory=dict)
    fraud_analysis_rate: float  # % of claims that have been analyzed
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class FraudDistribution(BaseModel):
    """Fraud score distribution buckets for analytics visualization."""
    buckets: Dict[str, int] = Field(default_factory=dict)
    total_assessed: int = 0
    high_risk_count: int = 0
    mean_score: float = 0.0
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class SLAMetrics(BaseModel):
    """SLA performance metrics."""
    average_days_to_decision: float | None = None
    by_type: Dict[str, float] = Field(default_factory=dict)
    claims_analyzed: int = 0
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ComplianceSummary(BaseModel):
    """Compliance health summary for auditors."""
    claims_with_fraud_analysis: int = 0
    high_risk_claims: int = 0
    human_review_required_count: int = 0
    compliance_rate: float = 0.0
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class CustomerRecentClaim(BaseModel):
    """A single claim row for the customer's recent activity feed."""
    id: str
    policy_number: str
    claim_type: str
    claim_amount: float | None
    status: str
    created_at: str
    updated_at: str


class CustomerMetrics(BaseModel):
    """Customer-facing dashboard — scoped to the authenticated user's claims only."""
    # Volume
    total_claims: int = 0
    active_claims: int = 0          # in pipeline: SUBMITTED → FRAUD_ANALYZED
    approved_claims: int = 0        # APPROVED
    settled_claims: int = 0         # SETTLED
    rejected_claims: int = 0        # REJECTED

    # Amounts
    total_claimed_amount: float = 0.0   # sum of claim_amount for all claims
    total_settled_amount: float = 0.0   # sum of claim_amount for SETTLED claims
    average_claim_amount: float = 0.0

    # Breakdowns
    status_breakdown: Dict[str, int] = Field(default_factory=dict)
    type_breakdown: Dict[str, int] = Field(default_factory=dict)  # HEALTH / MOTOR / REIMBURSEMENT

    # Recent activity
    recent_claims: list[CustomerRecentClaim] = Field(default_factory=list)  # newest 5

    # Attention items
    needs_action: list[str] = Field(default_factory=list)   # claim IDs in MANUAL_REVIEW_REQUIRED

    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
