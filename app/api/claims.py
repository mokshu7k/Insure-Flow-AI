"""Claims routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.claim import ClaimCreate, ClaimListResponse, ClaimResponse, ClaimStatusUpdate, ClaimUpdate
from app.services import claim_service

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("", response_model=ClaimResponse, status_code=201)
async def create_claim(
    payload: ClaimCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = await claim_service.create_claim(payload, str(current_user.id), current_user.role, db)
    return claim


@router.get("", response_model=ClaimListResponse)
async def list_claims(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await claim_service.list_claims(str(current_user.id), current_user.role, db, page, page_size, status)


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = await claim_service.get_claim(claim_id, str(current_user.id), current_user.role, db)
    return claim


@router.patch("/{claim_id}/status", response_model=ClaimResponse)
async def update_status(
    claim_id: str,
    payload: ClaimStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.rbac import require_any_role
    require_any_role(["INSURER_ADMIN", "CLAIM_ADJUSTER"])(current_user)
    claim = await claim_service.update_claim_status(
        claim_id, payload.status, str(current_user.id), current_user.role, db,
        adjuster_notes=payload.adjuster_notes,
    )
    return claim


@router.patch("/{claim_id}", response_model=ClaimResponse)
async def update_claim(
    claim_id: str,
    payload: ClaimUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Owner can update amount/description (used after OCR review in the wizard)."""
    claim = await claim_service.update_claim(claim_id, payload, str(current_user.id), current_user.role, db)
    return claim
