"""
Fraud Assessment model
"""
from sqlalchemy import Column, String, Float, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, GUID


class FraudAssessment(BaseModel):
    """
    Fraud assessment entity
    CRITICAL: Stores explainable AI reasoning for compliance
    """
    __tablename__ = "fraud_assessments"
    
    claim_id = Column(GUID(), ForeignKey("claims.id"), nullable=False, index=True)
    
    # Fraud score (0.0 to 1.0)
    fraud_score = Column(Float, nullable=False)
    
    # Explainable AI signals (JSON arrays)
    deterministic_signals_json = Column(JSON, nullable=False)  # Rule-based flags
    statistical_signals_json = Column(JSON, nullable=False)    # Anomaly detection results
    
    # Human-readable explanation (CRITICAL for compliance)
    explanation_text = Column(Text, nullable=False)
    
    # Feature snapshot for reproducibility (stores claim_context at analysis time)
    feature_snapshot_json = Column(JSON, nullable=True)
    
    # Relationship
    claim = relationship("Claim", back_populates="fraud_assessments")
    
    def __repr__(self):
        return f"<FraudAssessment claim={self.claim_id} score={self.fraud_score}>"