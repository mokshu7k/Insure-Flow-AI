"""Compliance schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ConsentGiveRequest(BaseModel):
    ip_address: Optional[str] = None


class ConsentStatusResponse(BaseModel):
    has_valid_consent: bool
    consent_version: str
    current_version: str


class AuditLogResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    actor_id: Optional[uuid.UUID]
    action_type: str
    entity_type: str
    entity_id: Optional[uuid.UUID]
    metadata_: dict[str, Any]
    ip_address: Optional[str]
    timestamp: datetime


class DeletionRequest(BaseModel):
    reason: Optional[str] = None


class DeletionResponse(BaseModel):
    accepted: bool
    message: str
