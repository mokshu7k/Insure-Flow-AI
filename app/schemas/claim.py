"""
Claim schemas (Pydantic)
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ClaimCreate(BaseModel):
    """Claim creation request"""
    policy_number: str = Field(..., min_length=5, max_length=100)
    claim_type: str = Field(..., pattern="^(HEALTH|MOTOR|REIMBURSEMENT)$")
    claim_amount: float = Field(default=0, ge=0)  # Optional during creation, set via update endpoint


class ClaimResponse(BaseModel):
    """Claim response"""
    id: str
    policy_number: str
    user_id: str
    claim_type: str
    claim_amount: float
    status: str
    fraud_score: Optional[float]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ClaimStatusUpdate(BaseModel):
    """Admin claim status update"""
    status: str = Field(..., pattern="^(APPROVED|REJECTED|MANUAL_REVIEW_REQUIRED)$")
    reason: Optional[str] = None


class ClaimListResponse(BaseModel):
    """Paginated claim list"""
    claims: List[ClaimResponse]
    total: int
    page: int
    page_size: int