"""
Legacy Adapter
Converts the new frozen FraudAssessmentResponse into the mutable
``FraudAnalysisResult`` schema expected by ``fraud_service.py`` and
existing tests.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.ai_agents.fraud.schemas import FraudAssessmentResponse
from app.schemas.fraud import FraudAnalysisResult


def to_legacy(response: FraudAssessmentResponse) -> FraudAnalysisResult:
    """
    Map the frozen engine response to the legacy mutable schema.

    Mapping rules:
    - ``fraud_score`` → as-is
    - ``deterministic_signals`` → ``deterministic_flags``
    - ``statistical_anomalies`` → ``statistical_flags``
    - ``behavioral_flags`` → ``behavioral_flags``
    - ``explanation`` → ``explanation``
    - ``metadata`` → preserved, with ``agent_scores`` key injected
      (expected by existing tests)

    Args:
        response: Immutable FraudAssessmentResponse from the engine.

    Returns:
        Mutable FraudAnalysisResult compatible with existing API/test contracts.
    """
    # Build the metadata dict the legacy consumers expect
    metadata: Dict[str, Any] = dict(response.metadata) if response.metadata else {}

    # The test suite asserts ``"agent_scores" in result.model_dump()``
    # via the metadata dict.  Populate from layer_scores if not present.
    if "agent_scores" not in metadata:
        metadata["agent_scores"] = {
            "rule_score": metadata.get("rule_score", 0.0),
            "anomaly_score": metadata.get("anomaly_score", 0.0),
            "behavior_score": metadata.get("behavior_score", 0.0),
            "narrative_score": metadata.get("narrative_score", 0.0),
        }

    return FraudAnalysisResult(
        fraud_score=response.fraud_score,
        deterministic_flags=list(response.deterministic_signals),
        statistical_flags=list(response.statistical_anomalies),
        behavioral_flags=list(response.behavioral_flags),
        explanation=response.explanation,
        metadata=metadata,
    )
