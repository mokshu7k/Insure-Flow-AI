"""Cashless claims service — QR generation, patient acceptance, insurer pre-authorization."""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.constants import AuditAction, CashlessStatus, ClaimStatus, ClaimType
from app.core.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.models.claim import Claim
from app.models.document import Document
from app.models.qr_token import QRToken
from app.services.audit_service import log_action


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_token(token: str) -> str:
    return hmac.new(settings.QR_SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()


def _make_qr_base64(data: str) -> str:
    """Generate a QR code PNG and return as base64 string.
    Falls back to a placeholder if qrcode library is not installed."""
    try:
        import qrcode  # type: ignore
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except ImportError:
        # Fallback: return a base64-encoded minimal placeholder
        return base64.b64encode(f"QR:{data}".encode()).decode("utf-8")


# ── Network Claims (for PROVIDER) ────────────────────────────────────────────

async def get_network_claims(
    provider_id: str,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Get all cashless claims assigned to this provider."""
    result = await db.execute(
        select(Claim)
        .where(
            Claim.provider_id == uuid.UUID(provider_id),
            Claim.claim_type == ClaimType.CASHLESS,
        )
        .order_by(Claim.created_at.desc())
    )
    claims = result.scalars().all()

    items = []
    for c in claims:
        # Check if any documents exist for this claim
        doc_result = await db.execute(
            select(func.count()).select_from(Document).where(Document.claim_id == c.id)
        )
        doc_count = doc_result.scalar() or 0

        # Check if a QR has already been generated
        qr_result = await db.execute(
            select(func.count()).select_from(QRToken).where(
                QRToken.claim_id == c.id,
                QRToken.status.isnot(None),  # cashless QR tokens have status set
            )
        )
        qr_count = qr_result.scalar() or 0

        items.append({
            "id": str(c.id),
            "user_id": str(c.user_id),
            "policy_number": c.policy_number,
            "claim_type": c.claim_type,
            "claim_amount": float(c.claim_amount) if c.claim_amount else None,
            "description": c.description,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "has_documents": doc_count > 0,
            "has_qr": qr_count > 0,
        })

    return items


# ── Generate QR (PROVIDER) ───────────────────────────────────────────────────

async def generate_cashless_qr(
    claim_id: str,
    provider_id: str,
    estimate_amount: float,
    patient_name: str,
    procedure_name: str,
    hospital_name: str,
    estimate_data: dict[str, Any] | None,
    db: AsyncSession,
) -> tuple[QRToken, str, str]:
    """
    Hospital generates a QR code for a cashless claim.
    Returns (qr_token_model, plaintext_token, qr_image_base64).
    """
    # Verify claim exists and belongs to this provider
    claim_result = await db.execute(
        select(Claim).where(Claim.id == uuid.UUID(claim_id))
    )
    claim = claim_result.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim not found")
    if str(claim.provider_id) != provider_id:
        raise PermissionDeniedError("This claim is not assigned to your hospital")
    if claim.claim_type != ClaimType.CASHLESS:
        raise BusinessRuleError("Only CASHLESS claims can use QR authorization")

    # Don't allow duplicate active QR tokens for the same claim
    existing = await db.execute(
        select(QRToken).where(
            QRToken.claim_id == uuid.UUID(claim_id),
            QRToken.status.in_([CashlessStatus.PENDING_REVIEW, CashlessStatus.ACCEPTED_BY_PATIENT]),
            QRToken.expires_at > datetime.now(tz=timezone.utc),
            QRToken.used == False,
        )
    )
    if existing.scalar_one_or_none():
        raise BusinessRuleError("An active cashless QR already exists for this claim")

    plaintext_token = _generate_token()
    token_hash = _hash_token(plaintext_token)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=settings.QR_TOKEN_EXPIRE_MINUTES)

    qr_token = QRToken(
        id=uuid.uuid4(),
        claim_id=uuid.UUID(claim_id),
        provider_id=uuid.UUID(provider_id),
        token_hash=token_hash,
        approved_amount=estimate_amount,
        used=False,
        expires_at=expires_at,
        status=CashlessStatus.PENDING_REVIEW,
        estimate_data=estimate_data or {},
        patient_name=patient_name,
        procedure_name=procedure_name,
        hospital_name=hospital_name,
    )
    db.add(qr_token)

    await log_action(
        db=db,
        action_type=AuditAction.CASHLESS_QR_GENERATED,
        entity_type="QR_TOKEN",
        actor_id=provider_id,
        entity_id=str(qr_token.id),
        metadata={
            "claim_id": claim_id,
            "estimate_amount": estimate_amount,
            "patient_name": patient_name,
            "procedure_name": procedure_name,
        },
    )

    await db.commit()
    await db.refresh(qr_token)

    qr_image_base64 = _make_qr_base64(plaintext_token)
    return qr_token, plaintext_token, qr_image_base64


# ── Scan QR (CUSTOMER) ───────────────────────────────────────────────────────

async def scan_cashless_qr(
    token: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Patient scans the QR. Returns estimate details for review.
    Does NOT change status — just reads.
    """
    token_hash = _hash_token(token)
    result = await db.execute(
        select(QRToken).where(QRToken.token_hash == token_hash)
    )
    qr_token = result.scalar_one_or_none()
    if not qr_token:
        raise NotFoundError("QR token not found or invalid")
    if qr_token.used:
        raise BusinessRuleError("This QR has already been used")
    if qr_token.expires_at < datetime.now(tz=timezone.utc):
        raise BusinessRuleError("This QR has expired")
    if qr_token.status not in (CashlessStatus.PENDING_REVIEW, None):
        raise BusinessRuleError(f"This QR is in status {qr_token.status} and cannot be scanned")

    # Get claim details
    claim_result = await db.execute(
        select(Claim).where(Claim.id == qr_token.claim_id)
    )
    claim = claim_result.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim associated with this QR not found")

    return {
        "qr_token_id": qr_token.id,
        "claim_id": claim.id,
        "policy_number": claim.policy_number,
        "claim_type": claim.claim_type,
        "patient_name": qr_token.patient_name,
        "procedure_name": qr_token.procedure_name,
        "hospital_name": qr_token.hospital_name,
        "estimate_amount": float(qr_token.approved_amount),
        "estimate_data": qr_token.estimate_data,
        "status": qr_token.status or "UNKNOWN",
        "expires_at": qr_token.expires_at,
    }


# ── Accept Estimate (CUSTOMER) ───────────────────────────────────────────────

async def accept_cashless_estimate(
    token: str,
    user_id: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """Patient accepts the cashless estimate. Moves QR to ACCEPTED_BY_PATIENT."""
    token_hash = _hash_token(token)
    result = await db.execute(
        select(QRToken).where(QRToken.token_hash == token_hash)
    )
    qr_token = result.scalar_one_or_none()
    if not qr_token:
        raise NotFoundError("QR token not found or invalid")
    if qr_token.used:
        raise BusinessRuleError("This QR has already been used")
    if qr_token.expires_at < datetime.now(tz=timezone.utc):
        raise BusinessRuleError("This QR has expired")
    if qr_token.status != CashlessStatus.PENDING_REVIEW:
        raise BusinessRuleError(f"Cannot accept QR in status {qr_token.status}")

    # Verify the claim belongs to this user
    claim_result = await db.execute(
        select(Claim).where(Claim.id == qr_token.claim_id)
    )
    claim = claim_result.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim not found")
    if str(claim.user_id) != user_id:
        raise PermissionDeniedError("This claim does not belong to you")

    # Update QR status
    qr_token.status = CashlessStatus.ACCEPTED_BY_PATIENT

    await log_action(
        db=db,
        action_type=AuditAction.CASHLESS_ACCEPTED,
        entity_type="QR_TOKEN",
        actor_id=user_id,
        entity_id=str(qr_token.id),
        metadata={"claim_id": str(claim.id), "estimate_amount": float(qr_token.approved_amount)},
    )

    await db.commit()
    await db.refresh(qr_token)

    return {
        "message": "Estimate accepted. Awaiting insurer pre-authorization.",
        "claim_id": claim.id,
        "status": qr_token.status,
    }


# ── Pending Authorizations (INSURER_ADMIN) ───────────────────────────────────

async def get_pending_authorizations(
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """List all QR tokens awaiting insurer pre-authorization."""
    result = await db.execute(
        select(QRToken)
        .where(QRToken.status == CashlessStatus.ACCEPTED_BY_PATIENT)
        .order_by(QRToken.created_at.desc())
    )
    tokens = result.scalars().all()

    items = []
    for t in tokens:
        claim_result = await db.execute(
            select(Claim).where(Claim.id == t.claim_id)
        )
        claim = claim_result.scalar_one_or_none()
        if not claim:
            continue

        items.append({
            "qr_token_id": t.id,
            "claim_id": claim.id,
            "policy_number": claim.policy_number,
            "claim_type": claim.claim_type,
            "patient_name": t.patient_name,
            "procedure_name": t.procedure_name,
            "hospital_name": t.hospital_name,
            "estimate_amount": float(t.approved_amount),
            "estimate_data": t.estimate_data,
            "status": t.status,
            "accepted_at": t.updated_at,
            "expires_at": t.expires_at,
        })

    return items


# ── Pre-Authorize / Reject (INSURER_ADMIN) ───────────────────────────────────

async def pre_authorize_cashless(
    qr_token_id: str,
    decision: str,
    actor_id: str,
    approved_amount: float | None,
    notes: str | None,
    db: AsyncSession,
) -> dict[str, Any]:
    """Insurer pre-authorizes or rejects a cashless claim."""
    result = await db.execute(
        select(QRToken).where(QRToken.id == uuid.UUID(qr_token_id))
    )
    qr_token = result.scalar_one_or_none()
    if not qr_token:
        raise NotFoundError("QR token not found")
    if qr_token.status != CashlessStatus.ACCEPTED_BY_PATIENT:
        raise BusinessRuleError(f"Cannot authorize QR in status {qr_token.status}")

    # Get associated claim
    claim_result = await db.execute(
        select(Claim).where(Claim.id == qr_token.claim_id)
    )
    claim = claim_result.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim not found")

    if decision == CashlessStatus.PRE_AUTHORIZED:
        qr_token.status = CashlessStatus.PRE_AUTHORIZED
        if approved_amount is not None:
            qr_token.approved_amount = approved_amount
        qr_token.insurer_notes = notes
        # Transition claim to PRE_AUTHORIZED
        claim.status = ClaimStatus.PRE_AUTHORIZED
        audit_action = AuditAction.CASHLESS_PRE_AUTHORIZED
        message = "Cashless claim pre-authorized successfully"
    elif decision == CashlessStatus.REJECTED:
        qr_token.status = CashlessStatus.REJECTED
        qr_token.insurer_notes = notes
        qr_token.used = True
        # Transition claim to REJECTED
        claim.status = ClaimStatus.REJECTED
        audit_action = AuditAction.CASHLESS_REJECTED
        message = "Cashless claim rejected"
    else:
        raise BusinessRuleError(f"Invalid decision: {decision}")

    await log_action(
        db=db,
        action_type=audit_action,
        entity_type="QR_TOKEN",
        actor_id=actor_id,
        entity_id=str(qr_token.id),
        metadata={
            "claim_id": str(claim.id),
            "decision": decision,
            "approved_amount": float(qr_token.approved_amount),
            "notes": notes,
        },
    )

    await db.commit()
    await db.refresh(qr_token)
    await db.refresh(claim)

    return {
        "message": message,
        "claim_id": claim.id,
        "qr_token_id": qr_token.id,
        "status": qr_token.status,
        "approved_amount": float(qr_token.approved_amount),
    }
