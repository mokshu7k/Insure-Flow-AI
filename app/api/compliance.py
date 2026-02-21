"""Compliance routes — consent, audit trail, deletion requests."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.compliance import (
    AuditLogResponse, ConsentGiveRequest, ConsentStatusResponse,
    DeletionRequest, DeletionResponse,
)
from app.services import compliance_service
from app.config import settings

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/consent", response_model=dict, status_code=201)
async def give_consent(
    request: Request,
    payload: ConsentGiveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ip = request.client.host if request.client else payload.ip_address
    await compliance_service.give_consent(str(current_user.id), ip, db)
    return {"message": "Consent recorded", "version": settings.CONSENT_VERSION}


@router.get("/consent", response_model=ConsentStatusResponse)
async def check_consent(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    has = await compliance_service.has_valid_consent(str(current_user.id), db)
    return ConsentStatusResponse(
        has_valid_consent=has,
        consent_version=settings.CONSENT_VERSION,
        current_version=settings.CONSENT_VERSION,
    )


@router.get("/audit", response_model=list[dict])
async def audit_trail(
    entity_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logs = await compliance_service.get_audit_trail(
        str(current_user.id), str(current_user.id), current_user.role, db,
        entity_id=entity_id, limit=limit,
    )
    return [
        {
            "id": str(log.id),
            "actor_id": str(log.actor_id) if log.actor_id else None,
            "action_type": log.action_type,
            "entity_type": log.entity_type,
            "entity_id": str(log.entity_id) if log.entity_id else None,
            "metadata": log.metadata_ if log.metadata_ else {},
            "timestamp": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.post("/delete-account", response_model=DeletionResponse)
async def request_deletion(
    payload: DeletionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await compliance_service.request_data_deletion(str(current_user.id), payload.reason, db)
    return result
