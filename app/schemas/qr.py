"""
QR Authorization schemas (Pydantic)
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class QRAuthorizationCreate(BaseModel):
    """Create QR authorization"""
    claim_id: str
    provider_id: str
    approved_limit: float = Field(..., gt=0)
    expiry_minutes: int = Field(default=30, ge=5, le=1440)  # 5 min to 24 hours


class QRAuthorizationResponse(BaseModel):
    """QR authorization response"""
    id: str
    claim_id: str
    provider_id: str
    approved_limit: float
    qr_token: str  # The actual token to encode in QR
    expires_at: datetime
    is_consumed: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class QRValidationRequest(BaseModel):
    """QR validation request"""
    qr_token: str


class QRValidationResponse(BaseModel):
    """QR validation response"""
    valid: bool
    claim_id: Optional[str] = None
    approved_limit: Optional[float] = None
    provider_id: Optional[str] = None
    message: str