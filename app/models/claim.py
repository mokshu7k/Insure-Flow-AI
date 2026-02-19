"""
Claim model
"""
from sqlalchemy import Column, String, Float, ForeignKey, Date
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, GUID


class Claim(BaseModel):
    """
    Insurance claim entity
    Core business object
    """
    __tablename__ = "claims"

    policy_number = Column(String(100), nullable=False, index=True)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    # Provider who submitted this claim (optional – set when a PROVIDER creates the claim)
    provider_id = Column(GUID(), ForeignKey("users.id"), nullable=True, index=True)
    claim_type = Column(String(50), nullable=False)  # HEALTH, MOTOR, REIMBURSEMENT
    claim_amount = Column(Float, nullable=False)
    # Policy expiry date – used by Layer 2 to fire CLAIM_NEAR_POLICY_EXPIRY
    policy_expiry_date = Column(Date, nullable=True)

    # Status workflow
    status = Column(String(50), nullable=False, default="SUBMITTED", index=True)
    # Statuses: SUBMITTED, OCR_PROCESSED, FRAUD_ANALYZED, MANUAL_REVIEW_REQUIRED, APPROVED, REJECTED, SETTLED

    # Fraud analysis result
    fraud_score = Column(Float, nullable=True)  # 0.0 to 1.0

    # Relationships
    user = relationship("User", back_populates="claims", foreign_keys=[user_id])
    provider = relationship("User", foreign_keys=[provider_id])
    documents = relationship("Document", back_populates="claim", cascade="all, delete-orphan")
    fraud_assessments = relationship("FraudAssessment", back_populates="claim", cascade="all, delete-orphan")
    qr_authorizations = relationship("QRAuthorization", back_populates="claim", cascade="all, delete-orphan")
    settlements = relationship("Settlement", back_populates="claim", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Claim {self.id} policy={self.policy_number} status={self.status}>"