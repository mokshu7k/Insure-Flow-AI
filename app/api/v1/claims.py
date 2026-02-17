"""
Claims API Routes
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from app.db.session import get_db
from app.schemas.claim import ClaimCreate, ClaimResponse, ClaimStatusUpdate, ClaimListResponse
from app.services.claim_service import ClaimService
from app.dependencies import get_current_user
from app.models.user import User
from app.core.rbac import require_role, Role

router = APIRouter()


@router.post("/", response_model=ClaimResponse, status_code=201)
def create_claim(
    claim_data: ClaimCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new claim
    
    CRITICAL: Enforces consent validation
    
    Requires: CUSTOMER role and valid consent
    """
    claim_service = ClaimService(db)
    claim = claim_service.create_claim(claim_data, current_user)
    
    return ClaimResponse.from_orm(claim)


@router.get("/", response_model=ClaimListResponse)
def list_claims(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List claims
    
    - CUSTOMER: Own claims only
    - ADMIN/AUDITOR: All claims
    """
    claim_service = ClaimService(db)
    claims = claim_service.get_user_claims(current_user, skip, limit, status)
    
    # Get total count (simplified - in production use efficient count query)
    total = len(claims)  # Simplified
    
    return ClaimListResponse(
        claims=[ClaimResponse.from_orm(c) for c in claims],
        total=total,
        page=skip // limit + 1,
        page_size=limit
    )


@router.get("/{claim_id}", response_model=ClaimResponse)
def get_claim(
    claim_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get claim by ID
    
    Authorization: Owner or Admin
    """
    claim_service = ClaimService(db)
    claim = claim_service.get_claim_by_id(uuid.UUID(claim_id), current_user)
    
    return ClaimResponse.from_orm(claim)


@router.put("/{claim_id}/status", response_model=ClaimResponse)
def update_claim_status(
    claim_id: str,
    status_update: ClaimStatusUpdate,
    current_user: User = Depends(require_role(Role.INSURER_ADMIN)),
    db: Session = Depends(get_db)
):
    """
    Update claim status (Admin only)
    
    CRITICAL: Human-in-the-loop enforcement
    All status changes logged in audit trail
    
    Requires: INSURER_ADMIN role
    """
    claim_service = ClaimService(db)
    claim = claim_service.update_claim_status(
        uuid.UUID(claim_id),
        status_update,
        current_user
    )
    
    return ClaimResponse.from_orm(claim)


@router.post("/{claim_id}/analyze", response_model=ClaimResponse)
def trigger_fraud_analysis(
    claim_id: str,
    current_user: User = Depends(require_role(Role.INSURER_ADMIN)),
    db: Session = Depends(get_db)
):
    """
    Trigger fraud analysis for claim
    
    Runs multi-agent fraud detection
    Updates claim with fraud score and status
    
    Requires: INSURER_ADMIN role
    """
    claim_service = ClaimService(db)
    claim = claim_service.trigger_fraud_analysis(uuid.UUID(claim_id))
    
    return ClaimResponse.from_orm(claim)