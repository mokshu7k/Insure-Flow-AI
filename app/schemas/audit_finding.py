"""Pydantic schemas for audit runs and findings (AUDITOR-role API responses)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AuditFindingResponse(BaseModel):
    id: UUID
    audit_run_id: UUID
    finding_type: str
    severity: str
    entity_type: str
    entity_id: str
    supporting_entity_ids: List[str] = Field(default_factory=list)
    description: str
    gemini_narrative: Optional[str] = None
    recommended_action: Optional[str] = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditRunResponse(BaseModel):
    id: UUID
    run_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    summary_narrative: Optional[str] = None
    errors: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditRunDetailResponse(AuditRunResponse):
    """AuditRun with all findings inlined."""
    findings: List[AuditFindingResponse] = Field(default_factory=list)


class AuditFindingListResponse(BaseModel):
    items: List[AuditFindingResponse]
    total: int
    page: int
    page_size: int


class AuditRunListResponse(BaseModel):
    items: List[AuditRunResponse]
    total: int
    page: int
    page_size: int
