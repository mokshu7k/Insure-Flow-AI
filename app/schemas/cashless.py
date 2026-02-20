"""Cashless claims Pydantic schemas – request/response models."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Generate QR (Provider) ────────────────────────────────────────────────────
class CashlessQRRequest(BaseModel):
    claim_id: str
    estimate_amount: float = Field(gt=0)
    patient_name: str = Field(min_length=1, max_length=255)
    procedure_name: str = Field(min_length=1, max_length=255)
    hospital_name: str = Field(min_length=1, max_length=255)
    estimate_data: dict[str, Any] | None = None


class CashlessQRResponse(BaseModel):
    id: str
    claim_id: str
    provider_id: str
    token: str
    approved_amount: float
    patient_name: str | None = None
    procedure_name: str | None = None
    hospital_name: str | None = None
    estimate_data: dict[str, Any] | None = None
    status: str
    expires_at: str
    qr_image_base64: str


# ── Scan QR (Customer) ───────────────────────────────────────────────────────
class CashlessScanResponse(BaseModel):
    qr_token_id: str
    claim_id: str
    policy_number: str
    claim_type: str
    patient_name: str | None = None
    procedure_name: str | None = None
    hospital_name: str | None = None
    estimate_amount: float
    estimate_data: dict[str, Any] | None = None
    status: str
    expires_at: str


# ── Accept Estimate (Customer) ───────────────────────────────────────────────
class CashlessAcceptRequest(BaseModel):
    token: str


class CashlessAcceptResponse(BaseModel):
    message: str
    claim_id: str
    status: str


# ── Pre-Authorize / Reject (Insurer) ─────────────────────────────────────────
class CashlessAuthorizationRequest(BaseModel):
    qr_token_id: str
    decision: str = Field(pattern=r"^(PRE_AUTHORIZED|REJECTED)$")
    approved_amount: float | None = None
    notes: str | None = None


class CashlessAuthorizationResponse(BaseModel):
    message: str
    claim_id: str
    qr_token_id: str
    status: str
    approved_amount: float | None = None


# ── List items ────────────────────────────────────────────────────────────────
class CashlessPendingItem(BaseModel):
    qr_token_id: str
    claim_id: str
    policy_number: str
    claim_type: str
    patient_name: str | None = None
    procedure_name: str | None = None
    hospital_name: str | None = None
    estimate_amount: float
    estimate_data: dict[str, Any] | None = None
    status: str
    accepted_at: str | None = None
    expires_at: str


class NetworkClaimItem(BaseModel):
    id: str
    user_id: str
    policy_number: str
    claim_type: str
    claim_amount: float | None = None
    description: str | None = None
    status: str
    created_at: str
    has_documents: bool
    has_qr: bool


class NetworkClaimsResponse(BaseModel):
    items: list[NetworkClaimItem]
    total: int
