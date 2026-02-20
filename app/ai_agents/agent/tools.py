"""
LangGraph agent tools — real DB-backed functions the LLM can invoke.
Each tool receives user_id and db_session via the graph state context,
passed through as part of the RunnableConfig.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


async def get_claim_status(claim_id: str, *, db, user_id: str) -> dict[str, Any]:
    """Return claim status and basic info for a specific claim ID."""
    from sqlalchemy import select
    from app.models.claim import Claim

    try:
        result = await db.execute(
            select(Claim).where(
                Claim.id == uuid.UUID(claim_id),
                Claim.user_id == uuid.UUID(user_id),
            )
        )
        claim = result.scalar_one_or_none()
        if not claim:
            return {"error": "Claim not found or not yours"}
        return {
            "claim_id": str(claim.id),
            "status": claim.status,
            "claim_type": claim.claim_type,
            "amount": float(claim.claim_amount),
            "fraud_score": float(claim.fraud_score) if claim.fraud_score else None,
        }
    except Exception as exc:
        logger.error("get_claim_status tool error: %s", exc)
        return {"error": str(exc)}


async def list_user_claims(*, db, user_id: str, limit: int = 5) -> dict[str, Any]:
    """Return recent claims for this user."""
    from sqlalchemy import select, desc
    from app.models.claim import Claim

    try:
        result = await db.execute(
            select(Claim)
            .where(Claim.user_id == uuid.UUID(user_id))
            .order_by(desc(Claim.created_at))
            .limit(limit)
        )
        claims = result.scalars().all()
        return {
            "claims": [
                {"id": str(c.id), "type": c.claim_type, "status": c.status, "amount": float(c.claim_amount)}
                for c in claims
            ]
        }
    except Exception as exc:
        return {"error": str(exc)}


async def get_fraud_explanation(claim_id: str, *, db, user_id: str) -> dict[str, Any]:
    """Return a human-readable fraud assessment explanation."""
    from sqlalchemy import select
    from app.models.fraud import FraudAssessment
    from app.models.claim import Claim

    try:
        # Verify ownership
        claim_result = await db.execute(
            select(Claim).where(Claim.id == uuid.UUID(claim_id), Claim.user_id == uuid.UUID(user_id))
        )
        if not claim_result.scalar_one_or_none():
            return {"error": "Claim not found"}

        result = await db.execute(
            select(FraudAssessment).where(FraudAssessment.claim_id == uuid.UUID(claim_id))
        )
        assessment = result.scalar_one_or_none()
        if not assessment:
            return {"info": "No fraud assessment run yet for this claim."}

        return {
            "fraud_score": float(assessment.fraud_score),
            "risk_level": assessment.risk_level,
            "explanation": assessment.explanation_text,
        }
    except Exception as exc:
        return {"error": str(exc)}


async def check_consent_status(*, db, user_id: str) -> dict[str, Any]:
    """Check if user has given valid consent."""
    from sqlalchemy import select, desc
    from app.models.consent import ConsentRecord
    from app.config import settings

    try:
        result = await db.execute(
            select(ConsentRecord)
            .where(
                ConsentRecord.user_id == uuid.UUID(user_id),
                ConsentRecord.consent_version == settings.CONSENT_VERSION,
            )
            .order_by(desc(ConsentRecord.created_at))
            .limit(1)
        )
        record = result.scalar_one_or_none()
        return {
            "has_consent": record is not None,
            "required_version": settings.CONSENT_VERSION,
        }
    except Exception as exc:
        return {"error": str(exc)}
