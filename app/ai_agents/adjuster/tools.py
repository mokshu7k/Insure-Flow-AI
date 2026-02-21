"""
Adjuster agent tools — read-only DB queries the LLM can invoke to build context.
All functions are async and accept db + adjuster_id via LangGraph config.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


async def get_full_claim(claim_id: str, *, db, adjuster_id: str) -> dict[str, Any]:
    """Fetch complete claim details including status, amount, type, description, timestamps."""
    from sqlalchemy import select
    from app.models.claim import Claim
    try:
        result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
        claim = result.scalar_one_or_none()
        if not claim:
            return {"error": "Claim not found"}
        return {
            "claim_id":      str(claim.id),
            "status":        claim.status,
            "claim_type":    claim.claim_type,
            "policy_number": claim.policy_number,
            "amount":        float(claim.claim_amount),
            "description":   claim.description,
            "fraud_score":   float(claim.fraud_score) if claim.fraud_score else None,
            "created_at":    str(claim.created_at)[:19] if claim.created_at else None,
            "updated_at":    str(claim.updated_at)[:19] if claim.updated_at else None,
        }
    except Exception as exc:
        logger.error("get_full_claim error: %s", exc)
        return {"error": str(exc)}


async def get_claimant_history(claim_id: str, *, db, adjuster_id: str) -> dict[str, Any]:
    """Fetch all historical claims by the same user — frequency and pattern analysis."""
    from sqlalchemy import select, desc
    from app.models.claim import Claim
    try:
        # First get the user_id from the current claim
        r = await db.execute(select(Claim.user_id).where(Claim.id == uuid.UUID(claim_id)))
        user_id = r.scalar_one_or_none()
        if not user_id:
            return {"error": "Claim not found"}

        result = await db.execute(
            select(Claim)
            .where(Claim.user_id == user_id)
            .order_by(desc(Claim.created_at))
            .limit(20)
        )
        claims = result.scalars().all()
        return {
            "user_id": str(user_id),
            "total_claims": len(claims),
            "claims": [
                {
                    "id":     str(c.id),
                    "type":   c.claim_type,
                    "status": c.status,
                    "amount": float(c.claim_amount),
                    "date":   str(c.created_at)[:10] if c.created_at else None,
                }
                for c in claims
            ],
        }
    except Exception as exc:
        return {"error": str(exc)}


async def get_document_extractions(claim_id: str, *, db, adjuster_id: str) -> dict[str, Any]:
    """Fetch all documents uploaded for the claim with their Gemini-extracted data."""
    from sqlalchemy import select
    from app.models.document import Document
    try:
        result = await db.execute(
            select(Document).where(Document.claim_id == uuid.UUID(claim_id))
        )
        docs = result.scalars().all()
        return {
            "document_count": len(docs),
            "documents": [
                {
                    "id":              str(d.id),
                    "type":            d.document_type,
                    "filename":        d.original_filename,
                    "extracted_data":  d.extracted_data,
                    "confidence":      float(d.extraction_confidence) if d.extraction_confidence else None,
                    "needs_review":    d.requires_manual_review,
                }
                for d in docs
            ],
        }
    except Exception as exc:
        return {"error": str(exc)}


async def get_fraud_assessment(claim_id: str, *, db, adjuster_id: str) -> dict[str, Any]:
    """Fetch the full fraud assessment including per-layer scores, signals, and AI explanation."""
    from sqlalchemy import select
    from app.models.fraud import FraudAssessment
    try:
        result = await db.execute(
            select(FraudAssessment).where(FraudAssessment.claim_id == uuid.UUID(claim_id))
        )
        fa = result.scalar_one_or_none()
        if not fa:
            return {"info": "No fraud assessment run yet for this claim."}
        return {
            "fraud_score":            float(fa.fraud_score),
            "risk_level":             fa.risk_level,
            "explanation":            fa.explanation_text,
            "layer_scores":           fa.layer_scores or {},
            "layer_details":          fa.layer_details or {},
            "deterministic_signals":  fa.deterministic_signals or [],
            "statistical_signals":    fa.statistical_signals or [],
            "behavioral_flags":       fa.behavioral_flags or [],
            "document_flags":         fa.document_flags or [],
            "network_flags":          fa.network_flags or [],
            "ai_degraded":            fa.ai_degraded_mode,
        }
    except Exception as exc:
        return {"error": str(exc)}


async def get_verification_report(claim_id: str, *, db, adjuster_id: str) -> dict[str, Any]:
    """Fetch the claim's AI verification report (cross-check of claim vs documents)."""
    from sqlalchemy import select
    from app.models.claim import Claim
    try:
        result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
        claim = result.scalar_one_or_none()
        if not claim:
            return {"error": "Claim not found"}
        if not hasattr(claim, "verified_data") or not claim.verified_data:
            return {"info": "No verification report yet. Run verify_claim_data first."}
        return claim.verified_data
    except Exception as exc:
        return {"error": str(exc)}


async def generate_report(claim_id: str, *, db, adjuster_id: str) -> dict[str, Any]:
    """
    Trigger comprehensive report generation. Pulls all context then asks Gemini
    to write a full Markdown report for the adjuster to process the claim.
    Returns {"report": "<markdown string>"}.
    """
    from app.config import settings
    from langchain_google_genai import ChatGoogleGenerativeAI

    # Gather all context
    claim       = await get_full_claim(claim_id, db=db, adjuster_id=adjuster_id)
    history     = await get_claimant_history(claim_id, db=db, adjuster_id=adjuster_id)
    docs        = await get_document_extractions(claim_id, db=db, adjuster_id=adjuster_id)
    fraud       = await get_fraud_assessment(claim_id, db=db, adjuster_id=adjuster_id)
    verification = await get_verification_report(claim_id, db=db, adjuster_id=adjuster_id)

    if not settings.GCP_API_KEY:
        return {"error": "No GCP_API_KEY configured"}

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GCP_API_KEY,
            temperature=0.2,
            max_output_tokens=5000,
        )

        prompt = f"""You are a senior insurance claims adjuster AI. Write a concise claim processing report in PLAIN TEXT only.

IMPORTANT FORMATTING RULES:
- Do NOT use any Markdown formatting (no #, *, **, ```, ---, etc.)
- Use plain text headings in ALL CAPS followed by a blank line
- Use simple dashes (-) for bullet points
- Use plain text for emphasis (e.g. write APPROVE not **APPROVE**)
- Keep the entire report under 3000 words

=== INPUT DATA ===

CLAIM:
{claim}

CLAIMANT HISTORY ({history.get('total_claims', 0)} total claims):
{history.get('claims', [])}

DOCUMENTS ({docs.get('document_count', 0)} uploaded):
{docs.get('documents', [])}

FRAUD ASSESSMENT:
Score: {fraud.get('fraud_score', 'N/A')} | Risk: {fraud.get('risk_level', 'N/A')}
Explanation: {fraud.get('explanation', 'N/A')}
Signals: deterministic={fraud.get('deterministic_signals', [])}, behavioral={fraud.get('behavioral_flags', [])}, document={fraud.get('document_flags', [])}

VERIFICATION REPORT:
{verification}

=== REPORT SECTIONS ===

Write the report with these exact sections:
1. CLAIMANT SUMMARY - Who they are, policy, history pattern
2. CLAIM DETAILS - What they are claiming and why
3. DOCUMENT ANALYSIS - What the AI extracted, any gaps or issues
4. DISCREPANCIES FOUND - Mismatches between claim and documents
5. FRAUD ASSESSMENT BREAKDOWN - Per-signal explanation in plain English
6. AI RECOMMENDATION - One of: APPROVE / FLAG_FOR_REVIEW / REJECT with reason
7. ACTION ITEMS - Specific steps the adjuster should take

Be concise, factual, and professional. No Markdown."""

        response = await llm.ainvoke(prompt)
        content = response.content
        if isinstance(content, list):
            content = "".join(
                b.get("text", "") if isinstance(b, dict) else str(b) for b in content
            ).strip()
        return {"report": content}
    except Exception as exc:
        logger.error("generate_report LLM error: %s", exc)
        return {"error": f"Report generation failed: {exc}"}
