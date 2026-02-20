"""Audit service — append-only log creation helper."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log_action(
    *,
    db: AsyncSession,
    action_type: str,
    entity_type: str,
    actor_id: str | None = None,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Create an immutable audit entry. Never update, never delete."""
    entry = AuditLog(
        id=uuid.uuid4(),
        actor_id=uuid.UUID(actor_id) if actor_id else None,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=uuid.UUID(entity_id) if entity_id else None,
        metadata_=metadata or {},
        ip_address=ip_address,
    )
    db.add(entry)
    # Note: caller must commit — audit logs should share the surrounding transaction
    return entry
