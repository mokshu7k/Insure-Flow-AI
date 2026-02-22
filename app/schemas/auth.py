"""Auth schemas."""
from __future__ import annotations

import uuid
from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "CUSTOMER"
    # DPDP Act, 2023 — explicit consent flag sent from the registration form.
    # Must be True; validation handled both client-side and here.
    consent_accepted: bool = False

    @field_validator("consent_accepted")
    @classmethod
    def consent_must_be_given(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "You must accept the Terms & Conditions and Privacy Policy to register."
            )
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        from app.core.constants import Role
        if v not in Role.ALL:
            raise ValueError(f"Role must be one of {Role.ALL}")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse



class RefreshResponse(BaseModel):
    message: str = "Token refreshed"
