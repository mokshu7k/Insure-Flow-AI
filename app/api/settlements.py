"""Settlement and QR routes."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.settlement import QRGenerateResponse, QRVerifyRequest, SettlementResponse
from app.services import settlement_service

router = APIRouter(tags=["settlements"])

# ── Settlements ────────────────────────────────────────────────────────────────
settle_router = APIRouter(prefix="/settlements")


@settle_router.post("/{claim_id}", response_model=SettlementResponse, status_code=201)
async def initiate_settlement(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.rbac import require_any_role
    require_any_role(["INSURER_ADMIN"])(current_user)
    settlement = await settlement_service.initiate_settlement(claim_id, str(current_user.id), db)
    return settlement


router.include_router(settle_router)

# ── QR Tokens ──────────────────────────────────────────────────────────────────
qr_router = APIRouter(prefix="/qr")


@qr_router.post("/generate/{claim_id}", response_model=QRGenerateResponse, status_code=201)
async def generate_qr(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.rbac import require_any_role
    require_any_role(["INSURER_ADMIN", "CLAIM_ADJUSTER"])(current_user)
    token, qr_model = await settlement_service.generate_qr_token(claim_id, str(current_user.id), db)
    return QRGenerateResponse(
        token=token,
        approved_amount=float(qr_model.approved_amount),
        expires_at=qr_model.expires_at,
        claim_id=qr_model.claim_id,
    )


@qr_router.post("/verify", response_model=dict)
async def verify_qr(
    payload: QRVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    qr = await settlement_service.verify_qr_token(payload.token, db)
    return {"valid": True, "approved_amount": float(qr.approved_amount), "claim_id": str(qr.claim_id)}


router.include_router(qr_router)
