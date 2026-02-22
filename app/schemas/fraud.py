"""Fraud schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class FraudAssessmentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    claim_id: uuid.UUID
    fraud_score: float
    risk_level: str
    deterministic_signals: list[Any]
    statistical_signals: list[Any]
    behavioral_flags: list[Any]
    document_flags: list[Any]
    network_flags: list[Any]
    layer_scores: Optional[dict[str, Any]] = None    # Per-layer complete info (score, flags, method, etc.)
    layer_details: Optional[dict[str, Any]] = None   # Full per-layer raw output (flags, method, ai_degraded)
    explanation_text: Optional[str]
    feature_snapshot: Optional[dict[str, Any]] = None
    config_version: Optional[str] = None
    ai_degraded_mode: bool
    ml_model_used: bool
    created_at: datetime



class FraudAnalysisQueued(BaseModel):
    message: str = "Fraud analysis queued"
    claim_id: uuid.UUID
