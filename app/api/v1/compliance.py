"""
Compliance API Routes
Consent, audit trail, access logs, data deletion.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.compliance.consent_validator import ConsentValidator, CONSENT_TEXT_V1
from app.compliance.retention_policy import RetentionPolicy
from app.compliance.access_monitor import AccessMonitor
from app.services.audit_service import AuditService
from app.dependencies import get_current_user
from app.models.user import User
from app.core.rbac import require_any_role, require_role, Role
from app.config import settings

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ConsentRequest(BaseModel):
    confirm: bool


class DeletionRequest(BaseModel):
    reason: str


# ── Consent ───────────────────────────────────────────────────────────────────

@router.get("/consent/text")
def get_consent_text():
    """
    Return the current canonical consent text for display.
    Public — no auth required.
    """
    return {
        "version": settings.CONSENT_VERSION,
        "text": CONSENT_TEXT_V1,          # ← module-level constant, no class needed
    }


@router.post("/consent/give")
def give_consent(
    body: ConsentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record consent. User must set confirm=true explicitly."""
    if not body.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm must be true to record consent",
        )
    validator = ConsentValidator(db)
    consent = validator.record_consent(current_user.id)
    return {
        "message": "Consent recorded",
        "consent_id": str(consent.id),
        "version": consent.consent_version,
        "timestamp": consent.timestamp.isoformat(),
    }


@router.get("/consent/status")
def consent_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    validator = ConsentValidator(db)
    has = validator.has_valid_consent(current_user.id)
    return {"user_id": str(current_user.id), "has_valid_consent": has, "can_submit_claims": has}


@router.get("/consent/history")
def consent_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    validator = ConsentValidator(db)
    consents = validator.get_consent_history(current_user.id)
    return [
        {
            "id": str(c.id),
            "version": c.consent_version,
            "timestamp": c.timestamp.isoformat(),
            "text_hash": c.consent_text_hash,
        }
        for c in consents
    ]


# ── Audit trail ───────────────────────────────────────────────────────────────

@router.get("/audit/trail")
def audit_trail(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(require_any_role([Role.INSURER_ADMIN, Role.AUDITOR])),
    db: Session = Depends(get_db),
):
    """Immutable audit trail. Requires INSURER_ADMIN or AUDITOR."""
    svc = AuditService(db)
    eid = uuid.UUID(entity_id) if entity_id else None
    logs = svc.get_audit_trail(entity_type=entity_type, entity_id=eid, limit=limit)
    return [
        {
            "id": str(log.id),
            "actor_id": str(log.actor_id) if log.actor_id else None,
            "action_type": log.action_type,
            "entity_type": log.entity_type,
            "entity_id": str(log.entity_id) if log.entity_id else None,
            "metadata": log.metadata_json,
            "timestamp": log.timestamp.isoformat(),
        }
        for log in logs
    ]


# ── Document access logs ──────────────────────────────────────────────────────

@router.get("/access-log/document/{document_id}")
def document_access_log(
    document_id: str,
    current_user: User = Depends(require_any_role([Role.INSURER_ADMIN, Role.AUDITOR])),
    db: Session = Depends(get_db),
):
    """HIPAA-aligned access history for a document."""
    monitor = AccessMonitor(db)
    logs = monitor.get_document_access_history(uuid.UUID(document_id))
    return [
        {
            "id": str(log.id),
            "user_id": str(log.user_id),
            "document_id": str(log.document_id),
            "action": log.action,
            "timestamp": log.timestamp.isoformat(),
        }
        for log in logs
    ]


# ── DPDP deletion ─────────────────────────────────────────────────────────────

@router.post("/deletion-request")
def deletion_request(
    body: DeletionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """DPDP right-to-erasure request. Evaluated against retention rules."""
    policy = RetentionPolicy(db)
    result = policy.process_deletion_request(
        user_id=current_user.id,
        requested_by=current_user.id,
    )
    result["request_reason"] = body.reason
    return result


@router.post("/retention/sweep")
def retention_sweep(
    current_user: User = Depends(require_role(Role.INSURER_ADMIN)),
    db: Session = Depends(get_db),
):
    """Manually trigger retention sweep. Requires INSURER_ADMIN."""
    policy = RetentionPolicy(db)
    return policy.run_retention_sweep()