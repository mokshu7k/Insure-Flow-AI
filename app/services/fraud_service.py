"""Fraud service — builds context, runs engine, persists results."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.models.claim import Claim
from app.models.document import Document
from app.models.fraud import FraudAssessment
from app.models.user_fraud_profile import UserFraudProfile
from app.ai_agents.fraud.orchestrator import FraudEngineOrchestrator
from app.services.audit_service import log_action

_engine = FraudEngineOrchestrator()


async def run_fraud_analysis(claim_id: str, actor_id: str, role: str, db: AsyncSession) -> FraudAssessment:
    # Ownership check
    claim_result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
    claim = claim_result.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim not found")
    if role == "CUSTOMER":
        raise PermissionDeniedError("Customers cannot trigger fraud analysis")

    # Load user profile for statistical context
    profile_result = await db.execute(
        select(UserFraudProfile).where(UserFraudProfile.user_id == claim.user_id)
    )
    profile = profile_result.scalar_one_or_none()

    # Load first document's extracted data (if any)
    doc_result = await db.execute(
        select(Document).where(Document.claim_id == uuid.UUID(claim_id)).limit(1)
    )
    doc = doc_result.scalar_one_or_none()

    context = {
        "claim_id": claim_id,
        "claim_amount": float(claim.claim_amount),
        "claim_type": claim.claim_type,
        "policy_number": claim.policy_number,
        "description": claim.description or "",
        "claim_created_at": str(claim.created_at)[:10] if claim.created_at else None,
        # From user profile
        "recent_claims_30d": profile.recent_claims_30d if profile else 0,
        "total_claim_amount_90d": float(profile.total_claim_amount_90d) if profile else 0.0,
        "fraud_flag_count": profile.fraud_flag_count if profile else 0,
        # Document context
        "extracted_data": doc.extracted_data if doc else {},
        "extracted_text": str(doc.extracted_data or {}),
    }

    response = _engine.analyze(context)

    # Upsert fraud assessment
    existing = await db.execute(
        select(FraudAssessment).where(FraudAssessment.claim_id == uuid.UUID(claim_id))
    )
    assessment = existing.scalar_one_or_none()
    if not assessment:
        assessment = FraudAssessment(id=uuid.uuid4(), claim_id=uuid.UUID(claim_id))
        db.add(assessment)

    assessment.fraud_score = response.fraud_score
    assessment.risk_level = response.risk_level
    assessment.layer_scores = response.layer_scores
    assessment.layer_details = response.layer_details
    assessment.deterministic_signals = response.deterministic_signals
    assessment.statistical_signals = response.statistical_signals
    assessment.behavioral_flags = response.behavioral_flags
    assessment.document_flags = response.document_flags
    assessment.network_flags = response.network_flags
    assessment.explanation_text = response.explanation_text
    assessment.feature_snapshot = response.feature_snapshot
    assessment.config_version = response.config_version
    assessment.ai_degraded_mode = response.ai_degraded_mode
    assessment.ml_model_used = response.ml_model_used

    # Update denormalized fraud_score on claim
    claim.fraud_score = response.fraud_score

    # Update user fraud profile
    if profile and response.risk_level in ("HIGH", "VERY_HIGH"):
        profile.fraud_flag_count += 1
        profile.last_updated = datetime.now(tz=timezone.utc)

    await log_action(
        db=db,
        action_type=AuditAction.FRAUD_ANALYSIS_RUN,
        entity_type="CLAIM",
        actor_id=actor_id,
        entity_id=claim_id,
        metadata={"score": response.fraud_score, "risk_level": response.risk_level},
    )
    await db.commit()
    await db.refresh(assessment)
    return assessment
