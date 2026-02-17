"""
QR Authorization API Routes
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.qr import (
    QRAuthorizationCreate,
    QRAuthorizationResponse,
    QRValidationRequest,
    QRValidationResponse
)
from app.services.qr_service import QRService
from app.dependencies import get_current_user
from app.models.user import User
from app.core.rbac import require_role, Role
from app.core.exceptions import InvalidQRTokenException, QRTokenAlreadyConsumedException

router = APIRouter()


@router.post("/authorize", response_model=QRAuthorizationResponse)
def create_qr_authorization(
    auth_data: QRAuthorizationCreate,
    current_user: User = Depends(require_role(Role.INSURER_ADMIN)),
    db: Session = Depends(get_db)
):
    """
    Create QR authorization for cashless claim
    
    CRITICAL SECURITY:
    - Signed token (HMAC-SHA256)
    - Time-limited
    - Single-use
    
    Requires: INSURER_ADMIN role
    """
    qr_service = QRService(db)
    authorization, qr_token = qr_service.create_authorization(auth_data, current_user.id)
    
    return QRAuthorizationResponse(
        id=str(authorization.id),
        claim_id=str(authorization.claim_id),
        provider_id=str(authorization.provider_id),
        approved_limit=authorization.approved_limit,
        qr_token=qr_token,  # Return token for QR code generation
        expires_at=authorization.expires_at,
        is_consumed=authorization.is_consumed,
        created_at=authorization.created_at
    )


@router.post("/validate", response_model=QRValidationResponse)
def validate_qr_authorization(
    validation_data: QRValidationRequest,
    current_user: User = Depends(require_role(Role.PROVIDER)),
    db: Session = Depends(get_db)
):
    """
    Validate and consume QR authorization
    
    CRITICAL VALIDATIONS:
    1. Token signature valid
    2. Not expired
    3. Not already consumed
    4. Provider matches
    
    Requires: PROVIDER role
    """
    qr_service = QRService(db)
    
    try:
        authorization = qr_service.validate_and_consume(validation_data, current_user.id)
        
        return QRValidationResponse(
            valid=True,
            claim_id=str(authorization.claim_id),
            approved_limit=authorization.approved_limit,
            provider_id=str(authorization.provider_id),
            message="Authorization valid and consumed"
        )
    
    except (InvalidQRTokenException, QRTokenAlreadyConsumedException) as e:
        return QRValidationResponse(
            valid=False,
            message=str(e.detail)
        )