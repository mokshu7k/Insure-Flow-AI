"""
Fraud Service
Orchestrates AI fraud analysis agents and persists assessments.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.ai_agents.fraud.orchestrator import FraudEngineOrchestrator
from app.ai_agents.fraud.privacy import sanitize
from app.core.constants import AuditAction
from app.models.claim import Claim
from app.models.fraud import FraudAssessment
from app.models.user_fraud_profile import UserFraudProfile
from app.schemas.fraud import FraudAnalysisResult, FraudAssessmentResponse
from app.services.audit_service import AuditService
from app.services.claim_context_builder import ClaimContextBuilder


class FraudService:
    """
    Fraud detection service.

    CRITICAL RESPONSIBILITIES:
    1. Orchestrate the six-layer fraud analysis pipeline.
    2. Store *sanitized* feature snapshots (P0 fix – no raw PII stored).
    3. Persist all new assessment fields (risk_level, per-layer flags, etc.).
    4. Write back to UserFraudProfile after every analysis (last_claim_date,
       total_claim_amount_90d) so future analyses are accurate.
    5. Never auto-reject – human-in-the-loop enforcement.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit_service = AuditService(db)
        self.orchestrator = FraudEngineOrchestrator()

    # ------------------------------------------------------------------
    # Core analysis
    # ------------------------------------------------------------------

    def analyze_claim(
        self,
        claim: Claim,
        privacy_mode: Optional[str] = None,
    ) -> FraudAnalysisResult:
        """
        Analyse a claim for fraud.

        Steps:
            1. Build enriched claim context (L4/L5 data included).
            2. Run the six-layer fraud engine.
            3. Store a sanitized feature snapshot (P0 – no raw PII).
            4. Persist FraudAssessment with all new fields.
            5. Write back last_claim_date + total_claim_amount_90d.
            6. Audit log.

        Args:
            claim: The ORM Claim object to analyse.
            privacy_mode: Optional override for the privacy sanitiser.

        Returns:
            FraudAnalysisResult with score, flags, and explanation.
        """
        # ---- Step 1: Build enriched context ----
        builder = ClaimContextBuilder(self.db)
        claim_context = builder.build(claim)

        # ---- Step 2: Run fraud engine ----
        engine_result = self.orchestrator.analyze(claim_context, privacy_mode=privacy_mode)

        # ---- Step 3: Sanitize feature snapshot (P0 fix – strip PII) ----
        sanitized_snapshot = sanitize(claim_context, mode="strict")

        # ---- Step 4: Persist FraudAssessment ----
        fraud_assessment = FraudAssessment(
            id=uuid.uuid4(),
            claim_id=claim.id,
            fraud_score=engine_result.fraud_score,
            risk_level=engine_result.risk_level,
            deterministic_signals_json=list(engine_result.deterministic_signals),
            statistical_signals_json=list(engine_result.statistical_anomalies),
            behavioral_flags_json=list(engine_result.behavioral_flags),
            document_flags_json=list(engine_result.document_flags),
            network_flags_json=list(engine_result.network_flags),
            explanation_text=engine_result.explanation,
            feature_snapshot_json=sanitized_snapshot,   # sanitized – no raw PII
            config_version=engine_result.config_version,
            baseline_version=engine_result.baseline_version,
            ai_degraded_mode=engine_result.ai_degraded_mode,
            ml_model_used=engine_result.ml_model_used,
        )
        self.db.add(fraud_assessment)

        # ---- Step 5: Write back to UserFraudProfile ----
        self._update_profile_after_analysis(claim)

        self.db.commit()
        self.db.refresh(fraud_assessment)

        # ---- Step 6: Audit log ----
        self.audit_service.log_action(
            actor_id=None,   # system action
            action_type=AuditAction.FRAUD_ANALYSIS_RUN,
            entity_type="CLAIM",
            entity_id=claim.id,
            metadata={
                "fraud_score":         engine_result.fraud_score,
                "risk_level":          engine_result.risk_level,
                "deterministic_flags": list(engine_result.deterministic_signals),
                "statistical_flags":   list(engine_result.statistical_anomalies),
                "behavioral_flags":    list(engine_result.behavioral_flags),
                "document_flags":      list(engine_result.document_flags),
                "network_flags":       list(engine_result.network_flags),
                "ai_degraded_mode":    engine_result.ai_degraded_mode,
                "ml_model_used":       engine_result.ml_model_used,
                "config_version":      engine_result.config_version,
            },
        )

        # Return internal result type for downstream callers
        return FraudAnalysisResult(
            fraud_score=engine_result.fraud_score,
            risk_level=engine_result.risk_level,
            deterministic_flags=list(engine_result.deterministic_signals),
            statistical_flags=list(engine_result.statistical_anomalies),
            behavioral_flags=list(engine_result.behavioral_flags),
            document_flags=list(engine_result.document_flags),
            network_flags=list(engine_result.network_flags),
            explanation=engine_result.explanation,
            metadata=dict(engine_result.metadata),
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_fraud_assessment(self, claim_id: uuid.UUID) -> Optional[FraudAssessment]:
        """
        Return the most recent FraudAssessment for a claim, or None.
        """
        return (
            self.db.query(FraudAssessment)
            .filter(FraudAssessment.claim_id == claim_id)
            .order_by(FraudAssessment.created_at.desc())
            .first()
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_profile_after_analysis(self, claim: Claim) -> None:
        """
        Write back rolling aggregates to UserFraudProfile so that future
        analyses for this user use up-to-date feature values.

        Updates:
          - last_claim_date → now (UTC)
          - total_claim_amount_90d += claim.claim_amount
        """
        profile = (
            self.db.query(UserFraudProfile)
            .filter(UserFraudProfile.user_id == claim.user_id)
            .first()
        )
        if profile is None:
            return  # profile will be created by ClaimContextBuilder.build()

        profile.last_claim_date = datetime.now(tz=timezone.utc)
        profile.total_claim_amount_90d = (
            (profile.total_claim_amount_90d or 0.0) + (claim.claim_amount or 0.0)
        )
        profile.last_updated = datetime.now(tz=timezone.utc)
        # Changes are flushed as part of the parent commit in analyze_claim()
