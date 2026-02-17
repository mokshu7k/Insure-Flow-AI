"""
Settlements API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from app.db.session import get_db
from app.schemas.settlement import SettlementCreate, SettlementResponse, SettlementStatusUpdate
from app.services.settlement_service import SettlementService
from app.models.user import User
from app.core.rbac import require_role, Role

router = APIRouter()


@router.post("/", response_model=SettlementResponse, status_code=status.HTTP_201_CREATED)
def initiate_settlement(
    settlement_data: SettlementCreate,
    current_user: User = Depends(require_role(Role.INSURER_ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Initiate claim settlement.

    Claim must be in APPROVED status.
    NO bank credentials stored — external gateway handles payment.

    Requires: INSURER_ADMIN
    """
    service = SettlementService(db)

    settlement = service.initiate_settlement(
        claim_id=uuid.UUID(settlement_data.claim_id),
        amount=settlement_data.amount,
        admin_id=current_user.id,
        external_reference=settlement_data.external_reference,
    )

    return SettlementResponse.from_orm(settlement)


@router.put("/{settlement_id}/status", response_model=SettlementResponse)
def update_settlement_status(
    settlement_id: str,
    update_data: SettlementStatusUpdate,
    current_user: User = Depends(require_role(Role.INSURER_ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Update settlement status.
    Called by payment gateway webhook or manual admin update.

    Statuses: PROCESSING, COMPLETED, FAILED

    Requires: INSURER_ADMIN
    """
    service = SettlementService(db)

    try:
        settlement = service.update_settlement_status(
            settlement_id=uuid.UUID(settlement_id),
            new_status=update_data.status,
            admin_id=current_user.id,
        )
        return SettlementResponse.from_orm(settlement)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/claim/{claim_id}", response_model=Optional[SettlementResponse])
def get_claim_settlement(
    claim_id: str,
    current_user: User = Depends(require_role(Role.INSURER_ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Get settlement record for a claim.

    Requires: INSURER_ADMIN
    """
    service = SettlementService(db)
    settlement = service.get_claim_settlement(uuid.UUID(claim_id))

    if not settlement:
        return None

    return SettlementResponse.from_orm(settlement)