"""Cashless claims API routes — QR generation, scanning, acceptance, pre-authorization."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import Role
from app.core.rbac import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.cashless import (
    CashlessAcceptRequest,
    CashlessAcceptResponse,
    CashlessAuthorizationRequest,
    CashlessAuthorizationResponse,
    CashlessPendingItem,
    CashlessQRRequest,
    CashlessQRResponse,
    CashlessScanResponse,
    NetworkClaimsResponse,
)
from app.services import cashless_service

router = APIRouter(prefix="/cashless", tags=["cashless"])


# ── Provider endpoints ────────────────────────────────────────────────────────

@router.get("/network-claims", response_model=NetworkClaimsResponse)
async def network_claims(
    current_user: User = Depends(require_role(Role.PROVIDER)),
    db: AsyncSession = Depends(get_db),
):
    """List all CASHLESS claims assigned to the current provider."""
    items = await cashless_service.get_network_claims(str(current_user.id), db)
    return {"items": items, "total": len(items)}


@router.post("/generate-qr", response_model=CashlessQRResponse)
async def generate_qr(
    payload: CashlessQRRequest,
    current_user: User = Depends(require_role(Role.PROVIDER)),
    db: AsyncSession = Depends(get_db),
):
    """Generate a cashless QR code for a claim."""
    qr_token, plaintext_token, qr_image = await cashless_service.generate_cashless_qr(
        claim_id=payload.claim_id,
        provider_id=str(current_user.id),
        estimate_amount=payload.estimate_amount,
        patient_name=payload.patient_name,
        procedure_name=payload.procedure_name,
        hospital_name=payload.hospital_name,
        estimate_data=payload.estimate_data,
        db=db,
    )
    return {
        "id": str(qr_token.id),
        "claim_id": str(qr_token.claim_id),
        "provider_id": str(qr_token.provider_id),
        "token": plaintext_token,
        "approved_amount": float(qr_token.approved_amount),
        "patient_name": qr_token.patient_name,
        "procedure_name": qr_token.procedure_name,
        "hospital_name": qr_token.hospital_name,
        "estimate_data": qr_token.estimate_data,
        "status": qr_token.status,
        "expires_at": qr_token.expires_at.isoformat(),
        "qr_image_base64": qr_image,
    }


# ── Customer endpoints ───────────────────────────────────────────────────────

@router.get("/scan/{token}", response_model=CashlessScanResponse)
async def scan_qr(
    token: str,
    current_user: User = Depends(require_role(Role.CUSTOMER)),
    db: AsyncSession = Depends(get_db),
):
    """Scan a cashless QR token and return estimate details."""
    data = await cashless_service.scan_cashless_qr(token, db)
    return {
        **data,
        "qr_token_id": str(data["qr_token_id"]),
        "claim_id": str(data["claim_id"]),
        "expires_at": data["expires_at"].isoformat() if hasattr(data["expires_at"], "isoformat") else str(data["expires_at"]),
    }


@router.post("/accept", response_model=CashlessAcceptResponse)
async def accept_estimate(
    payload: CashlessAcceptRequest,
    current_user: User = Depends(require_role(Role.CUSTOMER)),
    db: AsyncSession = Depends(get_db),
):
    """Patient accepts the cashless estimate."""
    result = await cashless_service.accept_cashless_estimate(
        token=payload.token,
        user_id=str(current_user.id),
        db=db,
    )
    return {
        **result,
        "claim_id": str(result["claim_id"]),
    }


# ── Insurer endpoints ────────────────────────────────────────────────────────

@router.get("/pending-authorizations", response_model=list[CashlessPendingItem])
async def pending_authorizations(
    current_user: User = Depends(require_role(Role.INSURER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """List all cashless claims awaiting insurer pre-authorization."""
    items = await cashless_service.get_pending_authorizations(db)
    return [
        {
            **item,
            "qr_token_id": str(item["qr_token_id"]),
            "claim_id": str(item["claim_id"]),
            "accepted_at": item["accepted_at"].isoformat() if item.get("accepted_at") and hasattr(item["accepted_at"], "isoformat") else item.get("accepted_at"),
            "expires_at": item["expires_at"].isoformat() if hasattr(item["expires_at"], "isoformat") else str(item["expires_at"]),
        }
        for item in items
    ]


@router.post("/pre-authorize", response_model=CashlessAuthorizationResponse)
async def pre_authorize(
    payload: CashlessAuthorizationRequest,
    current_user: User = Depends(require_role(Role.INSURER_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Insurer pre-authorizes or rejects a cashless claim."""
    result = await cashless_service.pre_authorize_cashless(
        qr_token_id=payload.qr_token_id,
        decision=payload.decision,
        actor_id=str(current_user.id),
        approved_amount=payload.approved_amount,
        notes=payload.notes,
        db=db,
    )
    return {
        **result,
        "claim_id": str(result["claim_id"]),
        "qr_token_id": str(result["qr_token_id"]),
    }
