"""
Settlement schemas (Pydantic v2)
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SettlementCreate(BaseModel):
    claim_id: str
    amount: float = Field(..., gt=0)
    external_reference: Optional[str] = None


class SettlementResponse(BaseModel):
    id: str
    claim_id: str
    settlement_reference_id: str
    amount: float
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj) -> "SettlementResponse":
        return cls(
            id=str(obj.id),
            claim_id=str(obj.claim_id),
            settlement_reference_id=obj.settlement_reference_id,
            amount=obj.amount,
            status=obj.status,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class SettlementStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(PROCESSING|COMPLETED|FAILED)$")