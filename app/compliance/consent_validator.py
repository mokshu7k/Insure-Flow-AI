"""
Compliance: Consent Validator
Single source of truth for all consent logic.
Used directly by claim_service, compliance API routes, and consent_service alias.
"""
import hashlib
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import AuditAction
from app.core.exceptions import ConsentNotGivenException
from app.models.consent import UserConsent

logger = logging.getLogger(__name__)

CONSENT_TEXT_V1 = (
    "InsureFlow-AI Data Collection & Processing Consent (Version 1.0)\n\n"
    "By submitting a claim on InsureFlow-AI, you expressly consent to:\n\n"
    "1. COLLECTION: Collection of your personal data including name, contact details, "
    "policy details, medical information, financial information, and documents "
    "submitted in support of your claim.\n\n"
    "2. PROCESSING: Processing of your personal data by automated systems including "
    "AI-assisted fraud analysis tools for the purpose of evaluating your claim.\n\n"
    "3. AI ANALYSIS: Use of explainable artificial intelligence to analyze your claim "
    "for potential fraud indicators. Any AI-generated score will be reviewed by "
    "a human insurance adjuster before any final decision is made.\n\n"
    "4. RETENTION: Retention of your data for a minimum of 7 years as required by "
    "applicable insurance regulations.\n\n"
    "5. SHARING: Sharing of your data with licensed healthcare providers, motor "
    "repair workshops, or other service providers directly involved in settling "
    "your claim.\n\n"
    "6. RIGHTS: You retain the right to access, correct, and request deletion of "
    "your data as permitted under applicable data protection laws.\n\n"
    "You may withdraw consent at any time, however withdrawal will prevent "
    "submission of new claims."
)

CONSENT_TEXTS: dict = {"1.0": CONSENT_TEXT_V1}


class ConsentValidator:
    """
    Single consent authority.
    Imported directly by claim_service, compliance routes, and seed script.
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Public API ──────────────────────────────────────────────────────────

    def enforce(self, user_id: uuid.UUID) -> None:
        """Raise ConsentNotGivenException if user has no valid consent."""
        if not self.has_valid_consent(user_id):
            logger.warning(f"Consent gate blocked user {user_id}")
            raise ConsentNotGivenException()

    # Alias so claim_service (which calls enforce_consent) works unchanged
    def enforce_consent(self, user_id: uuid.UUID) -> None:
        self.enforce(user_id)

    def has_valid_consent(self, user_id: uuid.UUID) -> bool:
        return (
            self.db.query(UserConsent)
            .filter(
                UserConsent.user_id == user_id,
                UserConsent.consent_version == settings.CONSENT_VERSION,
            )
            .first()
        ) is not None

    def record_consent(self, user_id: uuid.UUID) -> UserConsent:
        """
        Idempotent — safe to call multiple times.
        Hashes the canonical consent text and stores it.
        """
        text = CONSENT_TEXTS.get(settings.CONSENT_VERSION, CONSENT_TEXT_V1)
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        existing = (
            self.db.query(UserConsent)
            .filter(
                UserConsent.user_id == user_id,
                UserConsent.consent_version == settings.CONSENT_VERSION,
            )
            .first()
        )
        if existing:
            return existing

        consent = UserConsent(
            id=uuid.uuid4(),
            user_id=user_id,
            consent_version=settings.CONSENT_VERSION,
            consent_text_hash=text_hash,
            timestamp=datetime.utcnow(),
        )
        self.db.add(consent)

        # Circular-import-safe audit log (import inline)
        try:
            from app.services.audit_service import AuditService
            AuditService(self.db).log_action(
                actor_id=user_id,
                action_type=AuditAction.CONSENT_GIVEN,
                entity_type="CONSENT",
                entity_id=consent.id,
                metadata={"version": settings.CONSENT_VERSION},
            )
        except Exception:
            pass  # Audit failure must never block consent recording

        self.db.commit()
        self.db.refresh(consent)
        logger.info(f"Consent recorded: user={user_id} v={settings.CONSENT_VERSION}")
        return consent

    def get_consent_history(self, user_id: uuid.UUID) -> list:
        return (
            self.db.query(UserConsent)
            .filter(UserConsent.user_id == user_id)
            .order_by(UserConsent.timestamp.asc())
            .all()
        )

    def get_consent_text(self, version: Optional[str] = None) -> str:
        return CONSENT_TEXTS.get(version or settings.CONSENT_VERSION, CONSENT_TEXT_V1)