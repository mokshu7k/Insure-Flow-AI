"""Fraud service — bridge between API / DB and the LangGraph fraud agent.

Provides two entry points:
  • run_fraud_analysis()       — auto-picks first document on the claim
  • run_fraud_agent_analysis() — explicit document_id (called by agent-analyze endpoint)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models.claim import Claim
from app.models.claim_document import ClaimDocument
from app.models.fraud import FraudAssessment
from app.models.policy import Policy
from app.models.user_fraud_profile import UserFraudProfile
from app.services.audit_service import log_action
from app.ai_agents.fraud.graph import run_fraud_agent

logger = logging.getLogger(__name__)

# Node weight map — informational only.  The final score is now determined
# by Gemini in the aggregator node (not a weighted formula).  These weights
# are still sent to the frontend for display purposes.
NODE_WEIGHTS: dict[str, float] = {
    "extraction_integrity":       0.20,
    "cross_document_consistency": 0.15,
    "document_intelligence":      0.10,
    "image_forensics":            0.15,
    "document_content_fraud":     0.25,
    "behavioral_risk":            0.15,
}


# ── Helpers ──────────────────────────────────────────────────────────────────

_fernet_instance: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        _fernet_instance = Fernet(settings.ENCRYPTION_KEY.encode())
    return _fernet_instance


def _decrypt_document_file(storage_path: str) -> bytes:
    """Read and decrypt an encrypted document from disk."""
    encrypted = Path(storage_path).read_bytes()
    return _get_fernet().decrypt(encrypted)


async def _build_all_documents_data(
    claim_id: str, db: AsyncSession,
) -> list[dict[str, Any]]:
    """Gather all documents on a claim for cross-document checks (Node 2)."""
    result = await db.execute(
        select(ClaimDocument).where(ClaimDocument.claim_id == uuid.UUID(claim_id))
    )
    docs = list(result.scalars().all())
    return [
        {
            "document_id": str(d.id),
            "document_type_code": d.document_type_code,
            "extracted_data": d.extracted_data or {},
        }
        for d in docs
    ]


async def _build_policy_data(claim: Claim, db: AsyncSession) -> dict[str, Any] | None:
    """Load policy metadata for date-window / sum-insured checks."""
    if not claim.policy_number:
        return None
    result = await db.execute(
        select(Policy).where(Policy.policy_number == claim.policy_number)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        return None
    return {
        "start_date": str(policy.start_date) if policy.start_date else None,
        "end_date": str(policy.end_date) if policy.end_date else None,
        "sum_insured": float(policy.sum_insured) if policy.sum_insured else None,
    }


def _build_claim_metadata(
    claim: Claim, profile: UserFraudProfile | None,
) -> dict[str, Any]:
    """Build claim-level metadata dict expected by Node 6 (behavioural)."""
    snapshot = (claim.verified_data or {}).get("policy_snapshot", {})
    return {
        "claim_amount": float(claim.claim_amount),
        "claim_type": claim.claim_type,
        "sum_insured": snapshot.get("sum_insured"),
        "policy_start_date": snapshot.get("start_date"),
        "claim_created_at": str(claim.created_at)[:10] if claim.created_at else None,
        "recent_claims_30d": profile.recent_claims_30d if profile else 0,
        "total_claim_amount_90d": float(profile.total_claim_amount_90d) if profile else 0.0,
        "fraud_flag_count": profile.fraud_flag_count if profile else 0,
    }


# ── Persistence helper ───────────────────────────────────────────────────────

async def _persist_agent_result(
    claim_id: str,
    actor_id: str,
    result: dict[str, Any],
    claim: Claim,
    profile: UserFraudProfile | None,
    db: AsyncSession,
) -> FraudAssessment:
    """Map agent output → FraudAssessment row, persist, and return."""
    node_results: dict[str, Any] = result.get("node_results") or {}
    final_score = result.get("final_fraud_score") or 0.0
    risk_level = result.get("final_risk_level") or "MINIMAL"

    # Build layer_scores enriched with weight + flags for the frontend
    layer_scores: dict[str, Any] = {}
    for node_name, data in node_results.items():
        layer_scores[node_name] = {
            "score": data.get("score", 0),
            "weight": NODE_WEIGHTS.get(node_name, 0.0),
            "flags": data.get("flags", []),
            "layer": node_name,
        }

    # Collect signal categories from flags
    all_flags = []
    for data in node_results.values():
        all_flags.extend(data.get("flags", []))

    # Upsert
    existing = await db.execute(
        select(FraudAssessment).where(FraudAssessment.claim_id == uuid.UUID(claim_id))
    )
    assessment = existing.scalar_one_or_none()
    if not assessment:
        assessment = FraudAssessment(id=uuid.uuid4(), claim_id=uuid.UUID(claim_id))
        db.add(assessment)

    assessment.fraud_score = final_score
    assessment.risk_level = risk_level
    assessment.layer_scores = layer_scores
    assessment.layer_details = {k: v.get("details", {}) for k, v in node_results.items()}
    assessment.deterministic_signals = [f for f in all_flags if "MISMATCH" in f or "MISSING" in f]
    assessment.statistical_signals = [f for f in all_flags if "RATIO" in f or "AMOUNT" in f]
    assessment.behavioral_flags = [f for f in all_flags if "BEHAVIORAL" in f or "EARLY" in f or "PRIOR" in f]
    assessment.document_flags = [f for f in all_flags if "COPY_MOVE" in f or "PHASH" in f or "CONTENT" in f]
    assessment.network_flags = []
    assessment.explanation_text = result.get("risk_explanation", "")
    assessment.feature_snapshot = {
        "manual_review_required": result.get("manual_review_required", False),
        "manual_review_triggers": result.get("manual_review_triggers", []),
        "critical_signals": result.get("critical_signals", []),
        "analyzed_document_id": result.get("document_id"),
    }
    assessment.config_version = "agent-v1"
    assessment.ai_degraded_mode = False
    assessment.ml_model_used = False

    claim.fraud_score = final_score

    if profile and risk_level in ("HIGH", "VERY_HIGH"):
        profile.fraud_flag_count += 1
        profile.last_updated = datetime.now(tz=timezone.utc)

    # Attempt audit log — if it fails (e.g. FK constraint), rollback and
    # retry the commit without the audit row so the assessment is still saved.
    try:
        await log_action(
            db=db,
            action_type=AuditAction.FRAUD_ANALYSIS_RUN,
            entity_type="CLAIM",
            actor_id=actor_id,
            entity_id=claim_id,
            metadata={"score": final_score, "risk_level": risk_level},
        )
        await db.commit()
    except Exception as audit_exc:
        logger.warning(
            "Audit log failed for fraud analysis (claim=%s): %s — retrying commit without audit",
            claim_id, audit_exc,
        )
        await db.rollback()
        # Re-attach the assessment (rollback detached it)
        existing2 = await db.execute(
            select(FraudAssessment).where(FraudAssessment.claim_id == uuid.UUID(claim_id))
        )
        assessment = existing2.scalar_one_or_none()
        if not assessment:
            assessment = FraudAssessment(id=uuid.uuid4(), claim_id=uuid.UUID(claim_id))
            db.add(assessment)

        assessment.fraud_score = final_score
        assessment.risk_level = risk_level
        assessment.layer_scores = layer_scores
        assessment.layer_details = {k: v.get("details", {}) for k, v in node_results.items()}
        assessment.deterministic_signals = [f for f in all_flags if "MISMATCH" in f or "MISSING" in f]
        assessment.statistical_signals = [f for f in all_flags if "RATIO" in f or "AMOUNT" in f]
        assessment.behavioral_flags = [f for f in all_flags if "BEHAVIORAL" in f or "EARLY" in f or "PRIOR" in f]
        assessment.document_flags = [f for f in all_flags if "COPY_MOVE" in f or "PHASH" in f or "CONTENT" in f]
        assessment.network_flags = []
        assessment.explanation_text = result.get("risk_explanation", "")
        assessment.feature_snapshot = {
            "manual_review_required": result.get("manual_review_required", False),
            "manual_review_triggers": result.get("manual_review_triggers", []),
            "critical_signals": result.get("critical_signals", []),
            "analyzed_document_id": result.get("document_id"),
        }
        assessment.config_version = "agent-v1"
        assessment.ai_degraded_mode = False
        assessment.ml_model_used = False
        claim.fraud_score = final_score
        await db.commit()

    await db.refresh(assessment)
    return assessment


# ── Public entry points ──────────────────────────────────────────────────────

async def run_fraud_analysis(
    claim_id: str, actor_id: str, role: str, db: AsyncSession,
) -> FraudAssessment:
    """Auto-pick first document on the claim and run the fraud agent."""
    claim_result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
    claim = claim_result.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim not found")
    if role == "CUSTOMER":
        raise PermissionDeniedError("Customers cannot trigger fraud analysis")

    # Pick first document
    doc_result = await db.execute(
        select(ClaimDocument).where(ClaimDocument.claim_id == uuid.UUID(claim_id)).limit(1)
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("No documents uploaded for this claim")

    return await run_fraud_agent_analysis(claim_id, str(doc.id), actor_id, role, db)


async def run_fraud_agent_analysis(
    claim_id: str,
    document_id: str,
    actor_id: str,
    role: str,
    db: AsyncSession,
) -> FraudAssessment:
    """Run the 6-node LangGraph fraud agent on a specific document."""
    claim_result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
    claim = claim_result.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim not found")
    if role == "CUSTOMER":
        raise PermissionDeniedError("Customers cannot trigger fraud analysis")

    doc_result = await db.execute(
        select(ClaimDocument).where(ClaimDocument.id == uuid.UUID(document_id))
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document not found")

    profile_result = await db.execute(
        select(UserFraudProfile).where(UserFraudProfile.user_id == claim.user_id)
    )
    profile = profile_result.scalar_one_or_none()

    # Decrypt document bytes
    try:
        doc_bytes = _decrypt_document_file(doc.storage_path)
    except Exception:
        logger.warning("Could not decrypt document %s — using empty bytes", document_id)
        doc_bytes = b""

    # Build context for cross-doc and behavioural nodes
    all_documents_data = await _build_all_documents_data(claim_id, db)
    policy_data = await _build_policy_data(claim, db)
    claim_metadata = _build_claim_metadata(claim, profile)

    logger.info("Running fraud agent on claim=%s doc=%s", claim_id, document_id)

    result = await run_fraud_agent(
        claim_id=claim_id,
        document_id=document_id,
        document_bytes=doc_bytes,
        document_type_code=doc.document_type_code,
        existing_extracted_data=doc.extracted_data,
        all_documents_data=all_documents_data,
        policy_data=policy_data,
        claim_metadata=claim_metadata,
    )

    return await _persist_agent_result(
        claim_id=claim_id,
        actor_id=actor_id,
        result=result,
        claim=claim,
        profile=profile,
        db=db,
    )
