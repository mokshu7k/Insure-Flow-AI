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
    from app.models.claim_document import ClaimDocument
    try:
        result = await db.execute(
            select(ClaimDocument).where(ClaimDocument.claim_id == uuid.UUID(claim_id))
        )
        docs = result.scalars().all()
        return {
            "document_count": len(docs),
            "documents": [
                {
                    "id":              str(d.id),
                    "type":            d.document_type_code,
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


async def get_policy_details(claim_id: str, *, db, adjuster_id: str) -> dict[str, Any]:
    """Fetch the policy linked to the claim — coverage, schedule, T&C, deductible, copay."""
    from sqlalchemy import select
    from app.models.claim import Claim
    from app.models.policy import Policy
    try:
        r = await db.execute(select(Claim.policy_id).where(Claim.id == uuid.UUID(claim_id)))
        policy_id = r.scalar_one_or_none()
        if not policy_id:
            return {"info": "No policy linked to this claim."}
        pol_res = await db.execute(select(Policy).where(Policy.id == policy_id))
        p = pol_res.scalar_one_or_none()
        if not p:
            return {"info": "Policy record not found."}
        return {
            "policy_id":                  str(p.id),
            "policy_number":              p.policy_number,
            "policy_type":                p.policy_type,
            "status":                     p.status,
            "sum_insured":                float(p.sum_insured),
            "premium_amount":             float(p.premium_amount),
            "deductible":                 float(p.deductible) if p.deductible else None,
            "copay_percentage":           float(p.copay_percentage) if p.copay_percentage else None,
            "start_date":                 str(p.start_date),
            "end_date":                   str(p.end_date),
            "insured_name":               p.insured_name,
            "nominee_name":               p.nominee_name,
            "terms_conditions_version":   p.terms_conditions_version,
            "coverage_details":           p.coverage_details or {},
            "policy_schedule":            p.policy_schedule or {},
            "type_specific_data":         p.type_specific_data or {},
        }
    except Exception as exc:
        logger.error("get_policy_details error: %s", exc)
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
    claim        = await get_full_claim(claim_id, db=db, adjuster_id=adjuster_id)
    history      = await get_claimant_history(claim_id, db=db, adjuster_id=adjuster_id)
    docs         = await get_document_extractions(claim_id, db=db, adjuster_id=adjuster_id)
    fraud        = await get_fraud_assessment(claim_id, db=db, adjuster_id=adjuster_id)
    verification = await get_verification_report(claim_id, db=db, adjuster_id=adjuster_id)
    policy       = await get_policy_details(claim_id, db=db, adjuster_id=adjuster_id)

    if not settings.GCP_API_KEY:
        return {"error": "No GCP_API_KEY configured"}

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GCP_API_KEY,
            temperature=0.2,
            max_output_tokens=5000,
        )

        prompt = f"""You are a senior insurance claims adjuster AI. Write a comprehensive claim processing report in STRICT PLAIN TEXT following the exact format below.

════════════════════════════════════════
FORMAT SPECIFICATION (MUST FOLLOW EXACTLY)
════════════════════════════════════════

RULES:
- Do NOT use any Markdown (no #, *, **, `, ---, _underline_, etc.)
- Each section MUST begin with its exact ALL-CAPS heading on its own line, with NO leading spaces or dashes
- After the heading, leave ONE blank line, then write the section content
- Leave ONE blank line between sections
- Bullet points use "- " prefix (dash + space)
- BE CONCISE: max 2 sentences per paragraph, max 6 bullets per section, no filler
- Total report must be under 800 words

SECTION 1 HEADING:  CLAIMANT SUMMARY
  Content: 2-4 paragraph sentences describing the claimant, their policy details (number, type, sum insured, validity), and any notable history patterns.

SECTION 2 HEADING:  CLAIM DETAILS
  Content: ONLY key-value bullet pairs in this exact format:
    - Claim ID: <value>
    - Status: <value>
    - Claim Type: <value>
    - Policy Number: <value>
    - Claimed Amount: <value>
    - Description: <value>
    - Created At: <value>

SECTION 3 HEADING:  DOCUMENT ANALYSIS
  Content: For each document, write a bullet for the document header, then sub-bullets for extracted fields:
    - DOCUMENT_TYPE (original_filename.ext)
      - Extracted Patient Name: <value>
      - Extracted Diagnosis / Amount / Date / etc.: <value>
      - <any other extracted field>: <value>
      - Assessment: one sentence on whether this document supports the claim

SECTION 4 HEADING:  DISCREPANCIES FOUND
  Content: Bullet list of each mismatch found:
    - <Discrepancy category>: <description of the mismatch>

SECTION 5 HEADING:  FRAUD ASSESSMENT BREAKDOWN
  Content: Bullet list of fraud signals in plain English:
    - <Signal name>: <plain English explanation of why this raises concern>

SECTION 6 HEADING:  AI RECOMMENDATION
  Content: FIRST LINE must be ONE of these exact words only (no punctuation, no extra text on that line):
    APPROVE
    REJECT
    MANUAL REVIEW
  Then on the following lines, write 2-3 sentences explaining the reasoning. Your recommendation MUST
  explicitly reference whether the claimed event and amount are within the policy's covered risks,
  exclusions, room rent / sub-limits, deductible, and co-pay percentage from the POLICY COVERAGE section.

SECTION 7 HEADING:  ACTION ITEMS
  Content: Numbered action bullets (use "-" prefix, NOT numbers):
    - <Specific actionable step for the adjuster>
    - <Specific actionable step>

════════════════════════════════════════
INPUT DATA
════════════════════════════════════════

POLICY COVERAGE & TERMS:
Sum Insured: {policy.get('sum_insured', 'N/A')} | Deductible: {policy.get('deductible', 'None')} | Co-pay: {policy.get('copay_percentage', 0)}%
T&C Version: {policy.get('terms_conditions_version', 'N/A')} | Valid: {policy.get('start_date')} → {policy.get('end_date')}
Covered Risks: {policy.get('coverage_details', {}).get('covered', [])}
Exclusions: {policy.get('coverage_details', {}).get('exclusions', [])}
Key Limits: room_rent={policy.get('coverage_details', {}).get('room_rent_limit_per_day', 'N/A')}, icu={policy.get('coverage_details', {}).get('icu_limit_per_day', 'N/A')}, ambulance={policy.get('coverage_details', {}).get('ambulance_limit', 'N/A')}
Waiting Periods: initial={policy.get('coverage_details', {}).get('initial_waiting_period_days', 'N/A')}d, pre-existing={policy.get('coverage_details', {}).get('pre_existing_waiting_period_days', 'N/A')}d
Schedule: {policy.get('policy_schedule', {})}
Type-specific: {policy.get('type_specific_data', {})}

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

Now write the report following the format specification above exactly. Start directly with the first section heading CLAIMANT SUMMARY."""

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
