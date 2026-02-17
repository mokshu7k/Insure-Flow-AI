"""
Fraud Detection API Routes
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from app.db.session import get_db
from app.schemas.fraud import FraudAssessmentResponse
from app.services.fraud_service import FraudService
from app.dependencies import get_current_user
from app.models.user import User
from app.core.rbac import require_any_role, Role

router = APIRouter()


@router.get("/assessment/{claim_id}", response_model=FraudAssessmentResponse)
def get_fraud_assessment(
    claim_id: str,
    current_user: User = Depends(require_any_role([Role.INSURER_ADMIN, Role.AUDITOR])),
    db: Session = Depends(get_db)
):
    """
    Get fraud assessment for claim
    
    Returns explainable AI fraud analysis
    
    Requires: INSURER_ADMIN or AUDITOR role
    """
    fraud_service = FraudService(db)
    assessment = fraud_service.get_fraud_assessment(uuid.UUID(claim_id))
    
    if not assessment:
        return {"detail": "No fraud assessment found for this claim"}
    
    return FraudAssessmentResponse.from_orm(assessment)