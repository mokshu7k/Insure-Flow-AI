"""
Audit findings API — read-only endpoints for AUDITOR role only.

Routes
------
GET /audit/runs                    — paginated list of sweep runs
GET /audit/runs/{run_id}           — single run + all its findings
GET /audit/findings                — paginated findings with filters
GET /audit/findings/{finding_id}   — single finding with full evidence
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.rbac import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit_finding import (
    AuditFindingListResponse,
    AuditFindingResponse,
    AuditRunDetailResponse,
    AuditRunListResponse,
    AuditRunResponse,
)
from app.services.audit_finding_service import AuditFindingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/runs", response_model=AuditRunListResponse)
async def list_audit_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    from_date: Optional[datetime] = Query(None, description="ISO-8601 datetime"),
    to_date: Optional[datetime] = Query(None, description="ISO-8601 datetime"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("AUDITOR")),
):
    """List all audit sweep runs, newest first."""
    svc = AuditFindingService(db)
    runs, total = await svc.list_runs(
        page=page, page_size=page_size, from_date=from_date, to_date=to_date
    )
    return AuditRunListResponse(
        items=[AuditRunResponse.model_validate(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/runs/{run_id}", response_model=AuditRunDetailResponse)
async def get_audit_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("AUDITOR")),
):
    """Get a single audit run with all its findings inlined."""
    svc = AuditFindingService(db)
    run = await svc.get_run(run_id)
    if not run:
        raise NotFoundError(f"AuditRun {run_id} not found")
    return AuditRunDetailResponse.model_validate(run)


@router.get("/findings", response_model=AuditFindingListResponse)
async def list_audit_findings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    severity: Optional[str] = Query(
        None, description="CRITICAL | HIGH | MEDIUM | LOW"
    ),
    finding_type: Optional[str] = Query(
        None,
        description=(
            "ADJUSTER_PROVIDER_COLLUSION | PROVIDER_OVERBILLING | "
            "UNDERPAYMENT_PATTERN | HIGH_FRAUD_SCORE_APPROVED | "
            "ABNORMAL_SETTLEMENT_SPEED | SETTLEMENT_AMOUNT_DISCREPANCY | "
            "CLAIM_AMOUNT_GAP | PROVIDER_CLUSTER_ACTIVITY | "
            "USER_CLAIM_SURGE | DOCUMENT_INTEGRITY_FLAGS"
        ),
    ),
    entity_type: Optional[str] = Query(
        None, description="CLAIM | PROVIDER | ADJUSTER | USER | CLUSTER"
    ),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("AUDITOR")),
):
    """List findings across all runs with optional filters."""
    svc = AuditFindingService(db)
    findings, total = await svc.list_findings(
        page=page,
        page_size=page_size,
        severity=severity,
        finding_type=finding_type,
        entity_type=entity_type,
        from_date=from_date,
        to_date=to_date,
    )
    return AuditFindingListResponse(
        items=[AuditFindingResponse.model_validate(f) for f in findings],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/findings/{finding_id}", response_model=AuditFindingResponse)
async def get_audit_finding(
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("AUDITOR")),
):
    """Get a single finding with full Gemini narrative and evidence payload."""
    svc = AuditFindingService(db)
    finding = await svc.get_finding(finding_id)
    if not finding:
        raise NotFoundError(f"AuditFinding {finding_id} not found")
    return AuditFindingResponse.model_validate(finding)
