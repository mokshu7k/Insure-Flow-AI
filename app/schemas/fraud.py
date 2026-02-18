"""
Fraud Schemas (Pydantic)
Single source of truth for all fraud-related data contracts.

Contains:
    - Engine-internal layer results (DeterministicResult, StatisticalResult,
      NarrativeResult, AggregatedScore, FraudEngineResponse)
    - Service/API-facing schemas (FraudAnalysisResult, FraudAssessmentResponse)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Engine layer result schemas (frozen / immutable)
# ---------------------------------------------------------------------------
class DeterministicResult(BaseModel):
    """Output of Layer 1 -- deterministic rule engine."""
    model_config = ConfigDict(frozen=True)

    score: float
    signals: List[str]

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return min(1.0, max(0.0, v))


class StatisticalResult(BaseModel):
    """Output of Layer 2 -- statistical anomaly detector."""
    model_config = ConfigDict(frozen=True)

    score: float
    anomalies: List[str]

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return min(1.0, max(0.0, v))


class NarrativeResult(BaseModel):
    """Output of Layer 3 -- AI narrative generator."""
    model_config = ConfigDict(frozen=True)

    score: float
    structured_reasoning: Dict[str, object]
    ai_degraded_mode: bool = False

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return min(1.0, max(0.0, v))


# ---------------------------------------------------------------------------
# Aggregated score
# ---------------------------------------------------------------------------
class AggregatedScore(BaseModel):
    """Combined weighted output from all layers."""
    model_config = ConfigDict(frozen=True)

    final_score: float
    layer_scores: Dict[str, float]
    config_version: str
    baseline_version: str
    ai_degraded_mode: bool

    @field_validator("final_score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return min(1.0, max(0.0, v))


# ---------------------------------------------------------------------------
# Stable engine response (frozen / immutable)
# ---------------------------------------------------------------------------
class FraudEngineResponse(BaseModel):
    """
    Immutable fraud assessment produced by the engine orchestrator.
    CONFIG_VERSION is embedded in every instance.
    """
    model_config = ConfigDict(frozen=True)

    fraud_score: float
    deterministic_signals: List[str]
    statistical_anomalies: List[str]
    behavioral_flags: List[str]
    structured_reasoning: Dict[str, object]
    explanation: str
    config_version: str
    baseline_version: str
    ai_degraded_mode: bool
    metadata: Dict[str, object]

    @field_validator("fraud_score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return min(1.0, max(0.0, v))


# ---------------------------------------------------------------------------
# Service / API schemas (mutable)
# ---------------------------------------------------------------------------
class FraudAnalysisResult(BaseModel):
    """Internal fraud analysis result passed between services."""
    fraud_score: float
    deterministic_flags: List[str]
    statistical_flags: List[str]
    behavioral_flags: List[str]
    explanation: str
    metadata: Dict[str, Any]


class FraudAssessmentResponse(BaseModel):
    """Fraud assessment response returned by the API."""
    id: str
    claim_id: str
    fraud_score: float
    deterministic_signals: List[str]
    statistical_signals: List[str]
    explanation_text: str
    created_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm to handle JSON fields"""
        return cls(
            id=str(obj.id),
            claim_id=str(obj.claim_id),
            fraud_score=obj.fraud_score,
            deterministic_signals=obj.deterministic_signals_json or [],
            statistical_signals=obj.statistical_signals_json or [],
            explanation_text=obj.explanation_text,
            created_at=obj.created_at
        )