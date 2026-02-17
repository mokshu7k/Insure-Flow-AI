"""
Settlement model
"""
from sqlalchemy import Column, String, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Settlement(BaseModel):
    """
    Settlement/payment tracking
    NO bank credentials stored
    """
    __tablename__ = "settlements"
    
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False, index=True)
    
    # External reference (from payment gateway)
    settlement_reference_id = Column(String(255), nullable=False, unique=True)
    
    # Amount settled
    amount = Column(Float, nullable=False)
    
    # Status: PENDING, PROCESSING, COMPLETED, FAILED
    status = Column(String(50), nullable=False, default="PENDING")
    
    # Relationship
    claim = relationship("Claim", back_populates="settlements")
    
    def __repr__(self):
        return f"<Settlement {self.id} ref={self.settlement_reference_id} status={self.status}>"