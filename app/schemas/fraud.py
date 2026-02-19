"""
Fraud Schemas (Pydantic)
Single source of truth for all fraud-related data contracts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

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


class DocumentResult(BaseModel):
    """Output of Layer 4 -- document fraud detector."""
    model_config = ConfigDict(frozen=True)

    score: float
    flags: List[str]

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return min(1.0, max(0.0, v))


class NetworkResult(BaseModel):
    """Output of Layer 5 -- network / graph analysis."""
    model_config = ConfigDict(frozen=True)

    score: float
    flags: List[str]

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return min(1.0, max(0.0, v))


class MLResult(BaseModel):
    """Output of Layer 6 -- Isolation Forest ML layer."""
    model_config = ConfigDict(frozen=True)

    score: float
    ml_available: bool = False
    raw_decision: Optional[float] = None

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
    risk_level: str
    deterministic_signals: List[str]
    statistical_anomalies: List[str]
    behavioral_flags: List[str]
    document_flags: List[str]
    network_flags: List[str]
    structured_reasoning: Dict[str, object]
    explanation: str
    config_version: str
    baseline_version: str
    ai_degraded_mode: bool
    ml_model_used: bool
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
    risk_level: str = "UNKNOWN"
    deterministic_flags: List[str]
    statistical_flags: List[str]
    behavioral_flags: List[str]
    document_flags: List[str] = []
    network_flags: List[str] = []
    explanation: str
    metadata: Dict[str, Any]


class FraudAssessmentResponse(BaseModel):
    """Full fraud assessment response returned by the API."""
    id: str
    claim_id: str
    fraud_score: float
    risk_level: Optional[str] = None
    # Layer signals
    deterministic_signals: List[str]
    statistical_signals: List[str]
    behavioral_flags: List[str] = []
    document_flags: List[str] = []
    network_flags: List[str] = []
    # Human-readable
    explanation_text: str
    # Engine provenance
    config_version: Optional[str] = None
    baseline_version: Optional[str] = None
    ai_degraded_mode: Optional[bool] = None
    ml_model_used: Optional[bool] = None
    created_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm to handle JSON fields."""
        return cls(
            id=str(obj.id),
            claim_id=str(obj.claim_id),
            fraud_score=obj.fraud_score,
            risk_level=obj.risk_level,
            deterministic_signals=obj.deterministic_signals_json or [],
            statistical_signals=obj.statistical_signals_json or [],
            behavioral_flags=obj.behavioral_flags_json or [],
            document_flags=obj.document_flags_json or [],
            network_flags=obj.network_flags_json or [],
            explanation_text=obj.explanation_text,
            config_version=obj.config_version,
            baseline_version=obj.baseline_version,
            ai_degraded_mode=obj.ai_degraded_mode,
            ml_model_used=obj.ml_model_used,
            created_at=obj.created_at,
        )