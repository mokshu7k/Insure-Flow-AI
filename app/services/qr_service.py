"""
QR Authorization Service
Cashless claim authorization via QR codes
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid
import hashlib

from app.models.qr import QRAuthorization
from app.models.claim import Claim
from app.schemas.qr import QRAuthorizationCreate, QRValidationRequest
from app.utils.qr_signer import QRSigner
from app.core.exceptions import (
    ClaimNotFoundException,
    InvalidQRTokenException,
    QRTokenAlreadyConsumedException
)
from app.services.audit_service import AuditService
from app.core.constants import AuditAction


class QRService:
    """
    QR-based cashless authorization service
    
    CRITICAL SECURITY:
    1. Signed tokens (HMAC)
    2. Single-use enforcement
    3. Time-limited validity
    4. Provider validation
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)
        self.qr_signer = QRSigner()
    
    def create_authorization(
        self,
        auth_data: QRAuthorizationCreate,
        admin_user_id: uuid.UUID
    ) -> tuple[QRAuthorization, str]:
        """
        Create QR authorization
        
        Args:
            auth_data: Authorization data
            admin_user_id: Admin creating authorization
        
        Returns:
            Tuple of (QRAuthorization, qr_token)
        """
        # Verify claim exists
        claim = self.db.query(Claim).filter(Claim.id == auth_data.claim_id).first()
        if not claim:
            raise ClaimNotFoundException(auth_data.claim_id)
        
        # Generate signed token
        token_payload = {
            "claim_id": str(auth_data.claim_id),
            "provider_id": str(auth_data.provider_id),
            "approved_limit": auth_data.approved_limit,
            "nonce": uuid.uuid4().hex
        }
        
        qr_token = self.qr_signer.sign(token_payload, auth_data.expiry_minutes)
        
        # Hash token for storage (security: don't store plaintext)
        token_hash = hashlib.sha256(qr_token.encode()).hexdigest()
        
        # Calculate expiry
        expires_at = datetime.utcnow() + timedelta(minutes=auth_data.expiry_minutes)
        
        # Create authorization record
        authorization = QRAuthorization(
            id=uuid.uuid4(),
            claim_id=auth_data.claim_id,
            provider_id=auth_data.provider_id,
            approved_limit=auth_data.approved_limit,
            qr_token_hash=token_hash,
            expires_at=expires_at,
            is_consumed=False
        )
        
        self.db.add(authorization)
        self.db.commit()
        self.db.refresh(authorization)
        
        # Audit log
        self.audit_service.log_action(
            actor_id=admin_user_id,
            action_type=AuditAction.QR_GENERATED,
            entity_type="QR_AUTHORIZATION",
            entity_id=authorization.id,
            metadata={
                "claim_id": str(auth_data.claim_id),
                "provider_id": str(auth_data.provider_id),
                "approved_limit": auth_data.approved_limit,
                "expires_at": expires_at.isoformat()
            }
        )
        
        return authorization, qr_token
    
    def validate_and_consume(
        self,
        validation_data: QRValidationRequest,
        provider_user_id: uuid.UUID
    ) -> QRAuthorization:
        """
        Validate and consume QR token
        
        CRITICAL VALIDATIONS:
        1. Signature valid
        2. Not expired
        3. Not consumed
        4. Provider match
        
        Args:
            validation_data: Validation request
            provider_user_id: Provider validating token
        
        Returns:
            QRAuthorization object
        
        Raises:
            InvalidQRTokenException: If validation fails
        """
        # STEP 1: Verify signature and decode
        try:
            token_payload = self.qr_signer.verify(validation_data.qr_token)
        except Exception as e:
            raise InvalidQRTokenException("Invalid or tampered token")
        
        # STEP 2: Hash token for lookup
        token_hash = hashlib.sha256(validation_data.qr_token.encode()).hexdigest()
        
        # STEP 3: Find authorization record
        authorization = self.db.query(QRAuthorization).filter(
            QRAuthorization.qr_token_hash == token_hash
        ).first()
        
        if not authorization:
            raise InvalidQRTokenException("Authorization not found")
        
        # STEP 4: Check if already consumed
        if authorization.is_consumed:
            raise QRTokenAlreadyConsumedException()
        
        # STEP 5: Check expiry
        if datetime.utcnow() > authorization.expires_at:
            raise InvalidQRTokenException("Token has expired")
        
        # STEP 6: Verify provider match
        if str(authorization.provider_id) != str(provider_user_id):
            raise InvalidQRTokenException("Provider mismatch")
        
        # STEP 7: Mark as consumed (single-use enforcement)
        authorization.is_consumed = True
        self.db.commit()
        self.db.refresh(authorization)
        
        # Audit log
        self.audit_service.log_action(
            actor_id=provider_user_id,
            action_type=AuditAction.QR_VALIDATED,
            entity_type="QR_AUTHORIZATION",
            entity_id=authorization.id,
            metadata={
                "claim_id": str(authorization.claim_id),
                "approved_limit": authorization.approved_limit
            }
        )
        
        return authorization