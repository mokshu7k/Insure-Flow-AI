"""
Consent Service
DPDP Act compliance
"""
from sqlalchemy.orm import Session
import uuid
from datetime import datetime
import hashlib

from app.models.consent import UserConsent
from app.models.user import User
from app.config import settings
from app.core.exceptions import ConsentNotGivenException
from app.services.audit_service import AuditService
from app.core.constants import AuditAction


class ConsentService:
    """
    User consent management service
    CRITICAL: Consent required before claim submission
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)
    
    def record_consent(self, user_id: uuid.UUID, consent_text: str) -> UserConsent:
        """
        Record user consent
        
        Args:
            user_id: User ID
            consent_text: Full consent text
        
        Returns:
            UserConsent object
        """
        # Hash consent text for integrity
        consent_hash = hashlib.sha256(consent_text.encode()).hexdigest()
        
        # Create consent record
        consent = UserConsent(
            id=uuid.uuid4(),
            user_id=user_id,
            consent_version=settings.CONSENT_VERSION,
            consent_text_hash=consent_hash,
            timestamp=datetime.utcnow()
        )
        
        self.db.add(consent)
        self.db.commit()
        self.db.refresh(consent)
        
        # Audit log
        self.audit_service.log_action(
            actor_id=user_id,
            action_type=AuditAction.CONSENT_GIVEN,
            entity_type="CONSENT",
            entity_id=consent.id,
            metadata={"version": settings.CONSENT_VERSION}
        )
        
        return consent
    
    def has_valid_consent(self, user_id: uuid.UUID) -> bool:
        """
        Check if user has valid consent for current version
        
        Args:
            user_id: User ID
        
        Returns:
            bool: True if valid consent exists
        """
        consent = self.db.query(UserConsent).filter(
            UserConsent.user_id == user_id,
            UserConsent.consent_version == settings.CONSENT_VERSION
        ).first()
        
        return consent is not None
    
    def enforce_consent(self, user_id: uuid.UUID) -> None:
        """
        Enforce consent requirement
        Raises exception if consent not given
        
        Args:
            user_id: User ID
        
        Raises:
            ConsentNotGivenException: If consent not found
        """
        if not self.has_valid_consent(user_id):
            raise ConsentNotGivenException()
    
    def get_user_consents(self, user_id: uuid.UUID):
        """
        Get all consent records for user (historical)
        
        Args:
            user_id: User ID
        
        Returns:
            List of UserConsent objects
        """
        return self.db.query(UserConsent).filter(
            UserConsent.user_id == user_id
        ).order_by(UserConsent.timestamp.desc()).all()