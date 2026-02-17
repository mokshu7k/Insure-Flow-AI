"""
Fraud Engine Schemas
Strict Pydantic models for every layer boundary.
All score fields are float normalised to [0.0, 1.0].
"""
from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Layer result schemas
# ---------------------------------------------------------------------------
class DeterministicResult(BaseModel):
    """Output of Layer 1 – deterministic rule engine."""
    model_config = ConfigDict(frozen=True)

    score: float
    signals: List[str]

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return min(1.0, max(0.0, v))


class StatisticalResult(BaseModel):
    """Output of Layer 2 – statistical anomaly detector."""
    model_config = ConfigDict(frozen=True)

    score: float
    anomalies: List[str]

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return min(1.0, max(0.0, v))


class NarrativeResult(BaseModel):
    """Output of Layer 3 – AI narrative generator."""
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
# Stable orchestrator response (frozen / immutable)
# ---------------------------------------------------------------------------
class FraudAssessmentResponse(BaseModel):
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
