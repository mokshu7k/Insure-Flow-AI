"""Read-only query service backing the AUDITOR API endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_finding import AuditFinding, AuditRun


class AuditFindingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Runs ──────────────────────────────────────────────────────────────────

    async def list_runs(
        self,
        page: int = 1,
        page_size: int = 20,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> tuple[list[AuditRun], int]:
        q = select(AuditRun)
        if from_date:
            q = q.where(AuditRun.started_at >= from_date)
        if to_date:
            q = q.where(AuditRun.started_at <= to_date)

        total = (await self.db.execute(
            select(func.count()).select_from(q.subquery())
        )).scalar_one()

        q = (
            q.order_by(desc(AuditRun.started_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        runs = (await self.db.execute(q)).scalars().all()
        return list(runs), total

    async def get_run(self, run_id: uuid.UUID) -> Optional[AuditRun]:
        result = await self.db.execute(
            select(AuditRun).where(AuditRun.id == run_id)
        )
        return result.scalar_one_or_none()

    # ── Findings ─────────────────────────────────────────────────────────────

    async def list_findings(
        self,
        page: int = 1,
        page_size: int = 20,
        severity: Optional[str] = None,
        finding_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> tuple[list[AuditFinding], int]:
        q = select(AuditFinding)
        if severity:
            q = q.where(AuditFinding.severity == severity.upper())
        if finding_type:
            q = q.where(AuditFinding.finding_type == finding_type.upper())
        if entity_type:
            q = q.where(AuditFinding.entity_type == entity_type.upper())
        if from_date:
            q = q.where(AuditFinding.created_at >= from_date)
        if to_date:
            q = q.where(AuditFinding.created_at <= to_date)

        total = (await self.db.execute(
            select(func.count()).select_from(q.subquery())
        )).scalar_one()

        q = (
            q.order_by(desc(AuditFinding.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        findings = (await self.db.execute(q)).scalars().all()
        return list(findings), total

    async def get_finding(self, finding_id: uuid.UUID) -> Optional[AuditFinding]:
        result = await self.db.execute(
            select(AuditFinding).where(AuditFinding.id == finding_id)
        )
        return result.scalar_one_or_none()
