"""
Fraud Orchestrator (backward-compatibility wrapper)

Delegates all work to the new ``app.ai_agents.fraud`` engine while
preserving the original class name, method signature, and return type
so that ``fraud_service.py``, API routes, and existing tests continue
to work without any import changes.
"""
from typing import Dict, Any

from app.schemas.fraud import FraudAnalysisResult
from app.ai_agents.fraud.orchestrator import FraudEngineOrchestrator
from app.ai_agents.fraud.adapter import to_legacy


class FraudOrchestrator:
    """
    Multi-agent fraud analysis orchestrator (legacy interface).

    ARCHITECTURE:
    1. Rule-based validator (deterministic)
    2. Statistical anomaly detector
    3. Behavioral pattern analyzer
    4. Explanation generator (human-readable)

    CRITICAL: Results are EXPLAINABLE for compliance
    """

    def __init__(self) -> None:
        self._engine = FraudEngineOrchestrator()

    def analyze(self, claim_context: Dict[str, Any]) -> FraudAnalysisResult:
        """
        Run multi-agent fraud analysis.

        Args:
            claim_context: Claim data dictionary

        Returns:
            FraudAnalysisResult with score, flags, and explanation
        """
        engine_response = self._engine.analyze(claim_context)
        return to_legacy(engine_response)