"""Settlement and QR schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class SettlementCreate(BaseModel):
    claim_id: uuid.UUID
    amount: float
    notes: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class SettlementStatusUpdate(BaseModel):
    status: str
    external_reference: Optional[str] = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        from app.core.constants import SettlementStatus
        valid = {SettlementStatus.PROCESSING, SettlementStatus.COMPLETED, SettlementStatus.FAILED}
        if v not in valid:
            raise ValueError(f"status must be one of {valid}")
        return v


class SettlementResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    claim_id: uuid.UUID
    amount: float
    status: str
    settlement_reference: Optional[str]
    external_reference: Optional[str]
    completed_at: Optional[datetime]
    created_at: datetime


class QRGenerateResponse(BaseModel):
    token: str           # plaintext — sent to client once, stored as hash
    approved_amount: float
    expires_at: datetime
    claim_id: uuid.UUID


class QRVerifyRequest(BaseModel):
    token: str
