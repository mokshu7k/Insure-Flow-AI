"""Claims service — CRUD + state machine enforcement."""
from __future__ import annotations

import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction, ClaimStatus
from app.core.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.models.claim import Claim
from app.schemas.claim import ClaimCreate, ClaimListResponse, ClaimResponse, ClaimUpdate
from app.services.audit_service import log_action


async def create_claim(payload: ClaimCreate, user_id: str, role: str, db: AsyncSession) -> Claim:
    # PROVIDER users cannot file claims
    if role == "PROVIDER":
        raise PermissionDeniedError("Providers cannot file claims. Use the provider dashboard to view claims.")
    
    provider_id = None
    if payload.provider_id:
        provider_id = uuid.UUID(payload.provider_id)
    
    claim = Claim(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        provider_id=provider_id,
        policy_number=payload.policy_number,
        claim_type=payload.claim_type,
        claim_amount=payload.claim_amount,
        description=payload.description,
        status=ClaimStatus.SUBMITTED,
    )
    db.add(claim)
    await log_action(
        db=db,
        action_type=AuditAction.CLAIM_CREATED,
        entity_type="CLAIM",
        actor_id=user_id,
        entity_id=str(claim.id),
        metadata={"amount": payload.claim_amount, "type": payload.claim_type, "provider_id": str(provider_id) if provider_id else None},
    )
    await db.commit()
    await db.refresh(claim)
    return claim


async def get_claim(claim_id: str, user_id: str, role: str, db: AsyncSession) -> Claim:
    result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
    claim = result.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim not found")
    if role == "CUSTOMER" and str(claim.user_id) != user_id:
        raise PermissionDeniedError("Not your claim")
    if role == "PROVIDER" and str(claim.provider_id) != user_id:
        raise PermissionDeniedError("Not your claim")
    return claim


async def list_claims(
    user_id: str,
    role: str,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
) -> ClaimListResponse:
    query = select(Claim)
    if role == "CUSTOMER":
        query = query.where(Claim.user_id == uuid.UUID(user_id))
    elif role == "PROVIDER":
        # PROVIDER sees only claims associated with them
        query = query.where(Claim.provider_id == uuid.UUID(user_id))
    if status_filter:
        query = query.where(Claim.status == status_filter)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0

    query = query.order_by(Claim.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    claims = result.scalars().all()

    return ClaimListResponse(
        items=[ClaimResponse.model_validate(c) for c in claims],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


async def update_claim(
    claim_id: str, payload: ClaimUpdate, user_id: str, role: str, db: AsyncSession
) -> Claim:
    """Allow a CUSTOMER to update amount/description on their own SUBMITTED claim."""
    claim = await get_claim(claim_id, user_id, role, db)
    if role == "CUSTOMER" and claim.status != ClaimStatus.SUBMITTED:
        raise BusinessRuleError("Claim can only be edited while in SUBMITTED status")
    if payload.claim_amount is not None:
        claim.claim_amount = payload.claim_amount
    if payload.description is not None:
        claim.description = payload.description
    await log_action(
        db=db,
        action_type=AuditAction.CLAIM_CREATED,
        entity_type="CLAIM",
        actor_id=user_id,
        entity_id=claim_id,
        metadata={"updated_fields": payload.model_dump(exclude_none=True)},
    )
    await db.commit()
    await db.refresh(claim)
    return claim


async def update_claim_status(
    claim_id: str, new_status: str, actor_id: str, role: str, db: AsyncSession,
    adjuster_notes: str | None = None,
) -> Claim:
    claim = await get_claim(claim_id, actor_id, role, db)
    allowed = ClaimStatus.TRANSITIONS.get(claim.status, set())
    if new_status not in allowed:
        raise BusinessRuleError(
            f"Cannot transition claim from {claim.status} to {new_status}. "
            f"Allowed: {allowed or {'(terminal state)'}}"
        )
    old_status = claim.status
    claim.status = new_status
    if adjuster_notes is not None:
        claim.adjuster_notes = adjuster_notes
    await log_action(
        db=db,
        action_type=AuditAction.CLAIM_STATUS_CHANGED,
        entity_type="CLAIM",
        actor_id=actor_id,
        entity_id=claim_id,
        metadata={"from": old_status, "to": new_status, **(({"notes": adjuster_notes}) if adjuster_notes else {})},
    )
    await db.commit()
    await db.refresh(claim)
    return claim


async def verify_claim_data(claim_id: str, user_id: str, db: AsyncSession) -> dict:
    """
    Run a 'Verification Agent' (Gemini) to cross-check the claim against uploaded documents.
    Returns a structured verification report with discrepancies and a confidence score.
    """
    from app.models.document import Document
    from app.config import settings
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate
    import json

    # Fetch claim (using internal role to bypass if needed, but safe here)
    claim = await get_claim(claim_id, user_id, "ADJUSTER", db)
    
    result = await db.execute(select(Document).where(Document.claim_id == claim.id))
    documents = result.scalars().all()
    
    if not documents:
        return {"status": "skipped", "reason": "No documents to verify against"}

    # Prepare context for Gemini
    doc_context = []
    for d in documents:
        doc_context.append(f"Document ({d.document_type}): {d.extracted_data}")
    
    doc_text = "\n\n".join(doc_context)
    
    if not settings.GCP_API_KEY:
        return {"status": "error", "reason": "No AI key configured"}

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GCP_API_KEY,
            temperature=0.1,
        )

        prompt = PromptTemplate.from_template(
            "You are an expert Insurance Claims Adjuster. Verify this claim against the provided documents.\n"
            "Claim Details:\n"
            "- Amount: {amount}\n"
            "- Type: {type}\n"
            "- Policy: {policy}\n"
            "- Description: {description}\n\n"
            "Documents:\n{doc_text}\n\n"
            "Task:\n"
            "1. Check if the Claim Amount matches the total in documents.\n"
            "2. Check if the Dates match.\n"
            "3. Identify any missing information.\n"
            "4. Extract standardized fields for the final form.\n\n"
            "Return JSON: {{\"verification_status\": \"VERIFIED\" | \"FLAGGED\", \"confidence\": 0.0-1.0, \"discrepancies\": [\"reason1\"], \"verified_fields\": {{\"amount\": 123, \"date\": \"YYYY-MM-DD\"}}}}"
        )

        chain = prompt | llm
        response = await chain.ainvoke({
            "amount": float(claim.claim_amount),
            "type": claim.claim_type,
            "policy": claim.policy_number,
            "description": claim.description or "",
            "doc_text": doc_text[:20000]
        })
        
        content = response.content.replace("```json", "").replace("```", "").strip()
        verification_result = json.loads(content)
        
        # Persist to JSONB column (requires migration)
        # claim.verified_data = verification_result
        # await db.commit()
        # await db.refresh(claim)

        
        return verification_result

    except Exception as exc:
        return {"status": "error", "reason": str(exc)}

