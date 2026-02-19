"""
Fraud Detection API Routes
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
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


@router.post("/retrain", response_model=Dict[str, Any])
def retrain_fraud_model(
    samples: int = 5000,
    contamination: float = 0.10,
    current_user: User = Depends(require_any_role([Role.INSURER_ADMIN])),
) -> Dict[str, Any]:
    """
    Trigger Isolation Forest model retraining.

    Runs ``scripts/train_fraud_model.py`` synchronously in a subprocess,
    then reloads the new model artefact into memory.

    Query params:
        samples:       Number of synthetic training samples (default 5000).
        contamination: Expected anomaly fraction (default 0.10).

    Requires: INSURER_ADMIN role
    """
    cmd = [
        sys.executable,
        "scripts/train_fraud_model.py",
        "--samples", str(samples),
        "--contamination", str(contamination),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Model retraining timed out after 5 minutes.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retraining subprocess failed: {exc}",
        )

    if result.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"Training script exited with code {result.returncode}. "
                f"stderr: {result.stderr[-500:]}"
            ),
        )

    from app.ai_agents.fraud.ml_model import reload_model  # noqa: PLC0415
    reload_model()

    return {
        "status":        "success",
        "message":       "Isolation Forest model retrained and reloaded.",
        "samples":       samples,
        "contamination": contamination,
        "stdout":        result.stdout[-1000:],
    }