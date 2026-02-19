"""
Legacy Adapter
Converts the new frozen FraudEngineResponse into the mutable
``FraudAnalysisResult`` schema expected by ``fraud_service.py`` and
existing tests.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.schemas.fraud import FraudEngineResponse
from app.schemas.fraud import FraudAnalysisResult


def to_legacy(response: FraudEngineResponse) -> FraudAnalysisResult:
    """
    Map the frozen engine response to the legacy mutable schema.

    Args:
        response: Immutable FraudEngineResponse from the engine.

    Returns:
        Mutable FraudAnalysisResult compatible with existing API/test contracts.
    """
    metadata: Dict[str, Any] = dict(response.metadata) if response.metadata else {}

    if "agent_scores" not in metadata:
        metadata["agent_scores"] = {
            "rule_score":      metadata.get("rule_score", 0.0),
            "anomaly_score":   metadata.get("anomaly_score", 0.0),
            "behavior_score":  metadata.get("behavior_score", 0.0),
            "document_score":  metadata.get("document_score", 0.0),
            "network_score":   metadata.get("network_score", 0.0),
            "narrative_score": metadata.get("narrative_score", 0.0),
            "ml_score":        metadata.get("ml_score", 0.0),
        }

    return FraudAnalysisResult(
        fraud_score=response.fraud_score,
        risk_level=response.risk_level,
        deterministic_flags=list(response.deterministic_signals),
        statistical_flags=list(response.statistical_anomalies),
        behavioral_flags=list(response.behavioral_flags),
        document_flags=list(response.document_flags),
        network_flags=list(response.network_flags),
        explanation=response.explanation,
        metadata=metadata,
    )
