"""Policy schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator


class PolicyResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    policy_number: str
    policy_type: str
    status: str
    sum_insured: float
    premium_amount: float
    deductible: Optional[float]
    copay_percentage: Optional[float]
    start_date: date
    end_date: date
    insured_name: Optional[str]
    insured_dob: Optional[date]
    nominee_name: Optional[str]
    coverage_details: Optional[dict[str, Any]]
    policy_schedule: Optional[dict[str, Any]]
    terms_conditions_version: Optional[str]
    type_specific_data: Optional[dict[str, Any]]
    meta_data: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class PolicyListResponse(BaseModel):
    items: list[PolicyResponse]
    total: int
