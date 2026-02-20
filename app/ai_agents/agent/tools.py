"""
InsureFlow customer agent — DB-backed tool functions.

Each tool receives db and user_id via the graph state context (closure-injected in graph.py).
All functions are ownership-scoped: a customer can only see their own data.

Available tools (invoked by data_node via LangChain @tool wrappers):
  1. list_user_claims         - recent claims list with status + amount
  2. get_claim_status         - full single-claim deep-dive
  3. get_claim_documents      - OCR-extracted document info for a claim
  4. get_fraud_explanation    - fraud score, risk level, plain-English explanation
  5. get_settlement_info      - settlement status and reference for a claim
  6. get_claims_summary       - aggregate stats (totals, by status, by type)
  7. check_consent_status     - whether the user has valid consent on file
  8. get_claim_timeline       - ordered status-change events for a claim
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. List recent claims
# ---------------------------------------------------------------------------
async def list_user_claims(*, db, user_id: str, limit: int = 10) -> dict[str, Any]:
    """Return the user's most recent insurance claims with status and amount."""
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
            "total_returned": len(claims),
            "claims": [
                {
                    "id":           str(c.id),
                    "type":         c.claim_type,
                    "status":       c.status,
                    "amount":       float(c.claim_amount),
                    "policy":       c.policy_number,
                    "submitted_on": str(c.created_at)[:10] if c.created_at else None,
                    "fraud_score":  float(c.fraud_score) if c.fraud_score else None,
                }
                for c in claims
            ],
        }
    except Exception as exc:
        logger.error("list_user_claims error: %s", exc, exc_info=True)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# 2. Single claim deep-dive
# ---------------------------------------------------------------------------
async def get_claim_status(claim_id: str, *, db, user_id: str) -> dict[str, Any]:
    """Return full details for a specific claim owned by this user."""
    from sqlalchemy import select
    from app.models.claim import Claim
    try:
        result = await db.execute(
            select(Claim).where(
                Claim.id == uuid.UUID(claim_id),
                Claim.user_id == uuid.UUID(user_id),
            )
        )
        c = result.scalar_one_or_none()
        if not c:
            return {"error": "Claim not found or does not belong to you."}
        return {
            "claim_id":     str(c.id),
            "policy":       c.policy_number,
            "type":         c.claim_type,
            "status":       c.status,
            "amount":       float(c.claim_amount),
            "description":  c.description,
            "fraud_score":  float(c.fraud_score) if c.fraud_score else None,
            "submitted_on": str(c.created_at)[:19] if c.created_at else None,
            "last_updated": str(c.updated_at)[:19] if c.updated_at else None,
        }
    except Exception as exc:
        logger.error("get_claim_status error: %s", exc, exc_info=True)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# 3. Documents for a claim
# ---------------------------------------------------------------------------
async def get_claim_documents(claim_id: str, *, db, user_id: str) -> dict[str, Any]:
    """
    Return all documents uploaded for a claim (ownership-verified).
    Includes OCR-extracted data and confidence scores from Gemini.
    """
    from sqlalchemy import select
    from app.models.claim import Claim
    from app.models.document import Document
    try:
        cr = await db.execute(
            select(Claim.id).where(
                Claim.id == uuid.UUID(claim_id),
                Claim.user_id == uuid.UUID(user_id),
            )
        )
        if not cr.scalar_one_or_none():
            return {"error": "Claim not found or does not belong to you."}

        result = await db.execute(
            select(Document).where(Document.claim_id == uuid.UUID(claim_id))
        )
        docs = result.scalars().all()
        return {
            "claim_id":       claim_id,
            "document_count": len(docs),
            "documents": [
                {
                    "id":             str(d.id),
                    "type":           d.document_type,
                    "filename":       d.original_filename,
                    "extracted_data": d.extracted_data,
                    "confidence":     float(d.extraction_confidence) if d.extraction_confidence else None,
                    "needs_review":   d.requires_manual_review,
                }
                for d in docs
            ],
        }
    except Exception as exc:
        logger.error("get_claim_documents error: %s", exc, exc_info=True)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# 4. Fraud assessment
# ---------------------------------------------------------------------------
async def get_fraud_explanation(claim_id: str, *, db, user_id: str) -> dict[str, Any]:
    """
    Return a customer-friendly fraud assessment summary.
    Includes risk level, score, and the AI-generated plain-English explanation.
    """
    from sqlalchemy import select
    from app.models.claim import Claim
    from app.models.fraud import FraudAssessment
    try:
        cr = await db.execute(
            select(Claim.id).where(
                Claim.id == uuid.UUID(claim_id),
                Claim.user_id == uuid.UUID(user_id),
            )
        )
        if not cr.scalar_one_or_none():
            return {"error": "Claim not found or does not belong to you."}

        result = await db.execute(
            select(FraudAssessment).where(FraudAssessment.claim_id == uuid.UUID(claim_id))
        )
        fa = result.scalar_one_or_none()
        if not fa:
            return {"info": "No fraud assessment has been run yet for this claim."}
        return {
            "claim_id":    claim_id,
            "fraud_score": float(fa.fraud_score),
            "risk_level":  fa.risk_level,
            "explanation": fa.explanation_text,
            "flags": {
                "deterministic": fa.deterministic_signals or [],
                "behavioral":    fa.behavioral_flags or [],
                "document":      fa.document_flags or [],
            },
        }
    except Exception as exc:
        logger.error("get_fraud_explanation error: %s", exc, exc_info=True)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# 5. Settlement info
# ---------------------------------------------------------------------------
async def get_settlement_info(claim_id: str, *, db, user_id: str) -> dict[str, Any]:
    """
    Return settlement status for a claim: amount, reference number,
    processing status, and completion date if available.
    """
    from sqlalchemy import select
    from app.models.claim import Claim
    from app.models.settlement import Settlement
    try:
        cr = await db.execute(
            select(Claim.id).where(
                Claim.id == uuid.UUID(claim_id),
                Claim.user_id == uuid.UUID(user_id),
            )
        )
        if not cr.scalar_one_or_none():
            return {"error": "Claim not found or does not belong to you."}

        result = await db.execute(
            select(Settlement).where(Settlement.claim_id == uuid.UUID(claim_id))
        )
        s = result.scalar_one_or_none()
        if not s:
            return {"info": "No settlement has been initiated for this claim yet."}
        return {
            "claim_id":           claim_id,
            "settlement_amount":  float(s.amount),
            "status":             s.status,
            "reference":          s.settlement_reference,
            "external_reference": s.external_reference,
            "notes":              s.notes,
            "completed_at":       str(s.completed_at)[:19] if s.completed_at else None,
        }
    except Exception as exc:
        logger.error("get_settlement_info error: %s", exc, exc_info=True)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# 6. Claims aggregate summary
# ---------------------------------------------------------------------------
async def get_claims_summary(*, db, user_id: str) -> dict[str, Any]:
    """
    Return aggregate statistics across all of the user's claims:
    total count, total claimed amount, breakdown by status and claim type.
    """
    from sqlalchemy import select
    from app.models.claim import Claim
    try:
        result = await db.execute(
            select(Claim).where(Claim.user_id == uuid.UUID(user_id))
        )
        all_claims = result.scalars().all()
        if not all_claims:
            return {"info": "You have no claims on file."}

        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        total_amount = 0.0

        for c in all_claims:
            by_status[c.status] = by_status.get(c.status, 0) + 1
            by_type[c.claim_type] = by_type.get(c.claim_type, 0) + 1
            total_amount += float(c.claim_amount)

        return {
            "total_claims":  len(all_claims),
            "total_amount":  round(total_amount, 2),
            "by_status":     by_status,
            "by_type":       by_type,
        }
    except Exception as exc:
        logger.error("get_claims_summary error: %s", exc, exc_info=True)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# 7. Consent status
# ---------------------------------------------------------------------------
async def check_consent_status(*, db, user_id: str) -> dict[str, Any]:
    """Check whether the user has given valid data-processing consent."""
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
            "has_valid_consent": record is not None,
            "required_version":  settings.CONSENT_VERSION,
            "consented_on":      str(record.created_at)[:19] if record and record.created_at else None,
        }
    except Exception as exc:
        logger.error("check_consent_status error: %s", exc, exc_info=True)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# 8. Claim timeline
# ---------------------------------------------------------------------------
async def get_claim_timeline(claim_id: str, *, db, user_id: str) -> dict[str, Any]:
    """
    Build a chronological timeline of key events for a claim:
    submission, document uploads, fraud assessment, settlement.
    """
    from sqlalchemy import select
    from app.models.claim import Claim
    from app.models.document import Document
    from app.models.fraud import FraudAssessment
    from app.models.settlement import Settlement
    try:
        cr = await db.execute(
            select(Claim).where(
                Claim.id == uuid.UUID(claim_id),
                Claim.user_id == uuid.UUID(user_id),
            )
        )
        claim = cr.scalar_one_or_none()
        if not claim:
            return {"error": "Claim not found or does not belong to you."}

        events = []

        events.append({
            "event":  "Claim Submitted",
            "date":   str(claim.created_at)[:19] if claim.created_at else None,
            "detail": f"Type: {claim.claim_type}, Amount: Rs.{float(claim.claim_amount):,.2f}",
        })

        doc_result = await db.execute(
            select(Document).where(Document.claim_id == uuid.UUID(claim_id))
        )
        for d in doc_result.scalars().all():
            events.append({
                "event":  "Document Uploaded",
                "date":   str(d.created_at)[:19] if d.created_at else None,
                "detail": f"{d.document_type}: {d.original_filename}",
            })

        fa_result = await db.execute(
            select(FraudAssessment).where(FraudAssessment.claim_id == uuid.UUID(claim_id))
        )
        fa = fa_result.scalar_one_or_none()
        if fa:
            events.append({
                "event":  "Fraud Assessment Completed",
                "date":   str(fa.created_at)[:19] if fa.created_at else None,
                "detail": f"Risk: {fa.risk_level}, Score: {float(fa.fraud_score):.2f}",
            })

        s_result = await db.execute(
            select(Settlement).where(Settlement.claim_id == uuid.UUID(claim_id))
        )
        s = s_result.scalar_one_or_none()
        if s:
            events.append({
                "event":  "Settlement Initiated",
                "date":   str(s.created_at)[:19] if s.created_at else None,
                "detail": f"Amount: Rs.{float(s.amount):,.2f}, Status: {s.status}",
            })
            if s.completed_at:
                events.append({
                    "event":  "Settlement Completed",
                    "date":   str(s.completed_at)[:19],
                    "detail": f"Ref: {s.settlement_reference}",
                })

        events.append({
            "event":  "Current Status",
            "date":   str(claim.updated_at)[:19] if claim.updated_at else None,
            "detail": claim.status,
        })

        events.sort(key=lambda e: e["date"] or "")
        return {"claim_id": claim_id, "timeline": events}
    except Exception as exc:
        logger.error("get_claim_timeline error: %s", exc, exc_info=True)
        return {"error": str(exc)}

