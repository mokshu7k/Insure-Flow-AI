"""
QR Authorization model
"""
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class QRAuthorization(BaseModel):
    """
    QR-based cashless authorization
    Single-use, time-limited tokens
    """
    __tablename__ = "qr_authorizations"
    
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False, index=True)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Approved limit
    approved_limit = Column(Float, nullable=False)
    
    # Token security
    qr_token_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hash
    
    # Expiry and consumption
    expires_at = Column(DateTime, nullable=False)
    is_consumed = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    claim = relationship("Claim", back_populates="qr_authorizations")
    provider = relationship("User", foreign_keys=[provider_id])
    
    def __repr__(self):
        return f"<QRAuthorization claim={self.claim_id} consumed={self.is_consumed}>"