"""
Fraud Assessment model
"""
from sqlalchemy import Column, String, Float, ForeignKey, Text, JSON, Boolean
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

    # Risk level string (MINIMAL / LOW / MODERATE / HIGH / VERY_HIGH)
    risk_level = Column(String(20), nullable=True)

    # Explainable AI signals (JSON arrays)
    deterministic_signals_json = Column(JSON, nullable=False)   # Layer 1 – rule flags
    statistical_signals_json = Column(JSON, nullable=False)     # Layer 2 – anomaly flags
    behavioral_flags_json = Column(JSON, nullable=True)         # Layer 2 – behavioural flags
    document_flags_json = Column(JSON, nullable=True)           # Layer 4 – document flags
    network_flags_json = Column(JSON, nullable=True)            # Layer 5 – network/graph flags

    # Human-readable explanation (CRITICAL for compliance)
    explanation_text = Column(Text, nullable=False)

    # Feature snapshot for reproducibility (SANITIZED – no PII)
    feature_snapshot_json = Column(JSON, nullable=True)

    # Engine provenance
    config_version = Column(String(20), nullable=True)
    baseline_version = Column(String(20), nullable=True)
    ai_degraded_mode = Column(Boolean, nullable=True, default=False)
    ml_model_used = Column(Boolean, nullable=True, default=False)

    # Relationship
    claim = relationship("Claim", back_populates="fraud_assessments")

    def __repr__(self):
        return f"<FraudAssessment claim={self.claim_id} score={self.fraud_score} risk={self.risk_level}>"