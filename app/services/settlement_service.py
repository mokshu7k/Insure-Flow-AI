"""Settlement and QR token services."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.constants import AuditAction, ClaimStatus, SettlementStatus
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.claim import Claim
from app.models.fraud import FraudAssessment
from app.models.qr_token import QRToken
from app.models.settlement import Settlement
from app.services.audit_service import log_action


# ── Settlements ───────────────────────────────────────────────────────────────
async def initiate_settlement(
    claim_id: str, actor_id: str, db: AsyncSession
) -> Settlement:
    claim_result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
    claim = claim_result.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim not found")
    if claim.status != ClaimStatus.APPROVED:
        raise BusinessRuleError(f"Only APPROVED claims can be settled. Current: {claim.status}")

    # Guard: no double settlement
    existing = await db.execute(select(Settlement).where(Settlement.claim_id == uuid.UUID(claim_id)))
    if existing.scalar_one_or_none():
        raise BusinessRuleError("Settlement already initiated for this claim")

    # Guard: do not settle high-risk fraud  
    fraud_result = await db.execute(
        select(FraudAssessment).where(FraudAssessment.claim_id == uuid.UUID(claim_id))
    )
    assessment = fraud_result.scalar_one_or_none()
    if assessment and assessment.risk_level == "VERY_HIGH":
        raise BusinessRuleError("Settlement blocked: claim is VERY_HIGH fraud risk. Requires manual clearance.")

    ref = f"SETTL-{uuid.uuid4().hex[:12].upper()}"
    settlement = Settlement(
        id=uuid.uuid4(),
        claim_id=uuid.UUID(claim_id),
        initiated_by=uuid.UUID(actor_id),
        amount=float(claim.claim_amount),
        status=SettlementStatus.PROCESSING,
        settlement_reference=ref,
    )
    db.add(settlement)
    claim.status = ClaimStatus.SETTLED
    await log_action(
        db=db,
        action_type=AuditAction.SETTLEMENT_INITIATED,
        entity_type="SETTLEMENT",
        actor_id=actor_id,
        entity_id=str(settlement.id),
        metadata={"claim_id": claim_id, "amount": float(claim.claim_amount)},
    )
    await db.commit()
    await db.refresh(settlement)
    return settlement


# ── QR tokens ────────────────────────────────────────────────────────────────
def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_token(token: str) -> str:
    return hmac.new(settings.QR_SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()


async def generate_qr_token(claim_id: str, actor_id: str, db: AsyncSession) -> tuple[str, QRToken]:
    claim_result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
    claim = claim_result.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim not found")
    if claim.status != ClaimStatus.APPROVED:
        raise BusinessRuleError("QR tokens can only be generated for APPROVED claims")

    plaintext_token = _generate_token()
    token_model = QRToken(
        id=uuid.uuid4(),
        claim_id=uuid.UUID(claim_id),
        token_hash=_hash_token(plaintext_token),
        approved_amount=float(claim.claim_amount),
        used=False,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=settings.QR_TOKEN_EXPIRE_MINUTES),
    )
    db.add(token_model)
    await db.commit()
    await db.refresh(token_model)
    return plaintext_token, token_model


async def verify_qr_token(token: str, db: AsyncSession) -> QRToken:
    token_hash = _hash_token(token)
    result = await db.execute(select(QRToken).where(QRToken.token_hash == token_hash))
    qr = result.scalar_one_or_none()
    now = datetime.now(tz=timezone.utc)
    if not qr:
        raise BusinessRuleError("Invalid QR token")
    if qr.used:
        raise BusinessRuleError("QR token already used")
    if qr.expires_at < now:
        raise BusinessRuleError("QR token expired")
    qr.used = True
    await db.commit()
    return qr
