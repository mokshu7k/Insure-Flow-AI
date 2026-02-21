"""Compliance service — consent, DPDP deletion, audit trail."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BusinessRuleError
from app.models.consent import ConsentRecord
from app.models.audit import AuditLog

# Canonical consent text (hash this for tamper-evidence)
CONSENT_TEXT_V1 = (
    "I consent to InsureFlow AI processing my insurance claim data, "
    "including health and financial records, for the purpose of claim "
    "assessment and fraud detection under DPDP Act 2023 guidelines."
)


def _consent_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def give_consent(user_id: str, ip_address: str | None, db: AsyncSession) -> ConsentRecord:
    record = ConsentRecord(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        consent_version=settings.CONSENT_VERSION,
        consent_text_hash=_consent_hash(CONSENT_TEXT_V1),
        ip_address=ip_address,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def has_valid_consent(user_id: str, db: AsyncSession) -> bool:
    result = await db.execute(
        select(ConsentRecord)
        .where(
            ConsentRecord.user_id == uuid.UUID(user_id),
            ConsentRecord.consent_version == settings.CONSENT_VERSION,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def request_data_deletion(user_id: str, reason: str | None, db: AsyncSession) -> dict:
    """
    DPDP / GDPR right to erasure.
    For now: logs the request as an audit event. 
    Real erasure runs in a scheduled job to handle legal hold periods.
    """
    from app.services.audit_service import log_action
    await log_action(
        db=db,
        action_type="DELETION_REQUESTED",
        entity_type="USER",
        actor_id=user_id,
        entity_id=user_id,
        metadata={"reason": reason or "user_request", "retention_days": settings.DATA_RETENTION_DAYS},
    )
    await db.commit()
    return {"accepted": True, "message": f"Deletion request received. Data will be erased after the mandatory {settings.DATA_RETENTION_DAYS}-day retention period."}


async def get_audit_trail(
    user_id: str,
    actor_id: str,
    role: str,
    db: AsyncSession,
    limit: int = 50,
    entity_id: str | None = None,
) -> list[AuditLog]:
    q = select(AuditLog)
    if entity_id:
        # Filter to a specific claim / entity so each claim's audit trail is isolated
        try:
            q = q.where(AuditLog.entity_id == uuid.UUID(entity_id))
        except ValueError:
            q = q.where(AuditLog.entity_id == None)  # noqa: E711
    elif role == "CUSTOMER":
        q = q.where(AuditLog.actor_id == uuid.UUID(user_id))
    q = q.order_by(desc(AuditLog.created_at)).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())
