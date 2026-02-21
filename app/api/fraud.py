"""Fraud routes — trigger analysis and retrieve results."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.fraud import FraudAssessment
from app.models.user import User
from typing import Optional
from app.schemas.fraud import FraudAssessmentResponse, FraudAnalysisQueued
from app.services import fraud_service
import uuid

router = APIRouter(prefix="/fraud", tags=["fraud"])


@router.post("/analyze/{claim_id}", response_model=FraudAssessmentResponse, status_code=201)
async def analyze_claim(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run fraud engine on a claim. INSURER_ADMIN or CLAIM_ADJUSTER only."""
    from app.core.rbac import require_any_role
    require_any_role(["INSURER_ADMIN", "CLAIM_ADJUSTER"])(current_user)
    assessment = await fraud_service.run_fraud_analysis(claim_id, str(current_user.id), current_user.role, db)
    return assessment


@router.get("/{claim_id}", response_model=Optional[FraudAssessmentResponse])
async def get_assessment(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FraudAssessment).where(FraudAssessment.claim_id == uuid.UUID(claim_id))
    )
    return result.scalar_one_or_none()  # None → 200 null, no 404
