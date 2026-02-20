"""Claim schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class ClaimCreate(BaseModel):
    policy_number: str
    claim_type: str
    claim_amount: float
    description: Optional[str] = None

    @field_validator("claim_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        from app.core.constants import ClaimType
        if v not in ClaimType.ALL:
            raise ValueError(f"claim_type must be one of {ClaimType.ALL}")
        return v

    @field_validator("claim_amount")
    @classmethod
    def positive_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("claim_amount must be positive")
        return v


class ClaimStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        from app.core.constants import ClaimStatus
        if v not in ClaimStatus.TRANSITIONS:
            raise ValueError(f"Invalid status: {v}")
        return v


class ClaimUpdate(BaseModel):
    """Fields the owner can update after OCR review (wizard step 4)."""
    claim_amount: Optional[float] = None
    description: Optional[str] = None

    @field_validator("claim_amount")
    @classmethod
    def positive_amount(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("claim_amount must be positive")
        return v


class ClaimResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    policy_number: str
    claim_type: str
    claim_amount: float
    description: Optional[str]
    status: str
    fraud_score: Optional[float]
    created_at: datetime


class ClaimListResponse(BaseModel):
    items: list[ClaimResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
