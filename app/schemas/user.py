"""
User schemas (Pydantic v2)
"""
from __future__ import annotations
from pydantic import BaseModel
from typing import Optional


class UserUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None


class UserListResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}