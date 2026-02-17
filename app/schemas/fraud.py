"""
Fraud assessment schemas (Pydantic)
"""
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime


class FraudAssessmentResponse(BaseModel):
    """Fraud assessment response"""
    id: str
    claim_id: str
    fraud_score: float
    deterministic_signals: List[str]
    statistical_signals: List[str]
    explanation_text: str
    created_at: datetime
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm to handle JSON fields"""
        return cls(
            id=str(obj.id),
            claim_id=str(obj.claim_id),
            fraud_score=obj.fraud_score,
            deterministic_signals=obj.deterministic_signals_json or [],
            statistical_signals=obj.statistical_signals_json or [],
            explanation_text=obj.explanation_text,
            created_at=obj.created_at
        )


class FraudAnalysisResult(BaseModel):
    """Internal fraud analysis result"""
    fraud_score: float
    deterministic_flags: List[str]
    statistical_flags: List[str]
    behavioral_flags: List[str]
    explanation: str
    metadata: Dict[str, Any]