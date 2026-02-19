"""
Claim Service
Core business logic for insurance claims
"""
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime

from app.models.claim import Claim
from app.models.user import User
from app.models.user_fraud_profile import UserFraudProfile
from app.schemas.claim import ClaimCreate, ClaimStatusUpdate
from app.core.constants import ClaimStatus, AuditAction
from app.core.exceptions import (
    ClaimNotFoundException,
    UnauthorizedClaimAccessException,
    InvalidClaimStatusException
)
from app.services.audit_service import AuditService
from app.services.consent_service import ConsentService
from app.services.fraud_service import FraudService


class ClaimService:
    """
    Claim management service
    Enforces consent, triggers fraud analysis, manages status workflow
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)
        self.consent_service = ConsentService(db)
        self.fraud_service = FraudService(db)
    
    def create_claim(self, claim_data: ClaimCreate, user: User) -> Claim:
        """
        Create new claim
        
        CRITICAL ENFORCEMENT:
        1. Consent validation
        2. Audit logging
        
        Args:
            claim_data: Claim creation data
            user: Current user
        
        Returns:
            Created Claim object
        """
        # STEP 1: Enforce consent requirement
        self.consent_service.enforce_consent(user.id)
        
        # STEP 2: Create claim
        claim = Claim(
            id=uuid.uuid4(),
            policy_number=claim_data.policy_number,
            user_id=user.id,
            claim_type=claim_data.claim_type,
            claim_amount=claim_data.claim_amount,
            status=ClaimStatus.SUBMITTED.value,
            fraud_score=None  # Will be set after fraud analysis
        )
        
        self.db.add(claim)
        self.db.commit()
        self.db.refresh(claim)
        
        # STEP 3: Update user fraud profile (increment claim count)
        self._update_user_profile_on_claim(user.id)
        
        # STEP 4: Audit log
        self.audit_service.log_action(
            actor_id=user.id,
            action_type=AuditAction.CLAIM_SUBMITTED,
            entity_type="CLAIM",
            entity_id=claim.id,
            metadata={
                "policy_number": claim.policy_number,
                "claim_type": claim.claim_type,
                "amount": claim.claim_amount
            }
        )
        
        return claim
    
    def get_claim_by_id(self, claim_id: uuid.UUID, user: User) -> Claim:
        """
        Get claim by ID with authorization check
        
        Args:
            claim_id: Claim ID
            user: Current user
        
        Returns:
            Claim object
        
        Raises:
            ClaimNotFoundException: If claim not found
            UnauthorizedClaimAccessException: If user not authorized
        """
        claim = self.db.query(Claim).filter(Claim.id == claim_id).first()
        
        if not claim:
            raise ClaimNotFoundException(str(claim_id))
        
        # Authorization check
        if not self._can_access_claim(claim, user):
            raise UnauthorizedClaimAccessException()
        
        # Audit log
        self.audit_service.log_action(
            actor_id=user.id,
            action_type=AuditAction.CLAIM_VIEWED,
            entity_type="CLAIM",
            entity_id=claim.id
        )
        
        return claim
    
    def get_user_claims(
        self,
        user: User,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None
    ) -> List[Claim]:
        """
        Get claims for user (paginated)
        
        Args:
            user: Current user
            skip: Offset
            limit: Page size
            status: Optional status filter
        
        Returns:
            List of claims
        """
        query = self.db.query(Claim)
        
        # Role-based filtering
        if user.role == "CUSTOMER":
            query = query.filter(Claim.user_id == user.id)
        # INSURER_ADMIN and AUDITOR can see all claims
        
        # Status filter
        if status:
            query = query.filter(Claim.status == status)
        
        return query.order_by(Claim.created_at.desc()).offset(skip).limit(limit).all()
    
    def update_claim_status(
        self,
        claim_id: uuid.UUID,
        status_update: ClaimStatusUpdate,
        admin_user: User
    ) -> Claim:
        """
        Update claim status (admin only)
        
        CRITICAL: Human-in-the-loop enforcement
        
        Args:
            claim_id: Claim ID
            status_update: Status update data
            admin_user: Admin user performing update
        
        Returns:
            Updated Claim object
        """
        claim = self.db.query(Claim).filter(Claim.id == claim_id).first()
        
        if not claim:
            raise ClaimNotFoundException(str(claim_id))
        
        # Update status
        old_status = claim.status
        claim.status = status_update.status
        
        self.db.commit()
        self.db.refresh(claim)

        # Fraud feedback loop: when a claim is REJECTED with a high fraud
        # score, count it as a confirmed fraud event on the user's profile
        # so future assessments carry an accurate prior_fraud_flags count.
        if (
            status_update.status == "REJECTED"
            and claim.fraud_score is not None
            and claim.fraud_score >= 0.70
        ):
            self._record_confirmed_fraud(claim.user_id)
        
        # Audit log (CRITICAL for compliance)
        self.audit_service.log_action(
            actor_id=admin_user.id,
            action_type=AuditAction.CLAIM_APPROVED if status_update.status == "APPROVED" else AuditAction.CLAIM_REJECTED,
            entity_type="CLAIM",
            entity_id=claim.id,
            metadata={
                "old_status": old_status,
                "new_status": status_update.status,
                "reason": status_update.reason,
                "fraud_score": claim.fraud_score
            }
        )
        
        return claim
    
    def update_claim_amount(
        self,
        claim_id: uuid.UUID,
        amount: float,
        user: User
    ) -> Claim:
        """
        Update claim amount (for draft claims)
        
        Only claim owner can update amount before final submission.
        Automatically triggers fraud analysis after amount is set.
        
        Args:
            claim_id: Claim ID
            amount: New claim amount
            user: User performing update
        
        Returns:
            Updated Claim object
        """
        claim = self.db.query(Claim).filter(Claim.id == claim_id).first()
        
        if not claim:
            raise ClaimNotFoundException(str(claim_id))
        
        # Only owner can update
        if str(claim.user_id) != str(user.id):
            raise UnauthorizedClaimAccessException()
        
        # Only allow update if claim is in SUBMITTED or OCR_PROCESSED status
        if claim.status not in [ClaimStatus.SUBMITTED.value, ClaimStatus.OCR_PROCESSED.value]:
            raise InvalidClaimStatusException(
                f"Cannot update amount for claim in status: {claim.status}"
            )
        
        # Update amount
        old_amount = claim.claim_amount
        claim.claim_amount = amount
        
        # Move to UNDER_REVIEW status
        claim.status = ClaimStatus.UNDER_REVIEW.value
        
        self.db.commit()
        self.db.refresh(claim)
        
        # Audit log
        self.audit_service.log_action(
            actor_id=user.id,
            action_type=AuditAction.CLAIM_SUBMITTED,
            entity_type="CLAIM",
            entity_id=claim.id,
            metadata={
                "action": "amount_updated_and_submitted",
                "old_amount": old_amount,
                "new_amount": amount
            }
        )
        
        # Automatically trigger fraud analysis (results only visible to admin)
        try:
            self._run_fraud_analysis_async(claim)
        except Exception as e:
            # Log error but don't fail the submission
            import logging
            logging.getLogger(__name__).error(f"Fraud analysis failed: {e}")
        
        return claim
    
    def _run_fraud_analysis_async(self, claim: Claim) -> None:
        """
        Run fraud analysis on the claim.
        Results are stored but not shown to customer.
        """
        fraud_result = self.fraud_service.analyze_claim(claim)
        
        # Update claim with fraud score
        claim.fraud_score = fraud_result.fraud_score
        
        # Update status based on fraud score
        if fraud_result.fraud_score >= 0.7:
            claim.status = ClaimStatus.MANUAL_REVIEW_REQUIRED.value
            # Increment prior_fraud_flags for high-risk claims
            self._update_user_profile_on_fraud(claim.user_id)
        else:
            claim.status = ClaimStatus.FRAUD_ANALYZED.value
        
        self.db.commit()
        self.db.refresh(claim)
    
    def trigger_fraud_analysis(self, claim_id: uuid.UUID) -> Claim:
        """
        Trigger fraud analysis for claim
        
        CRITICAL: This is where AI meets compliance
        
        Args:
            claim_id: Claim ID
        
        Returns:
            Updated Claim object
        """
        claim = self.db.query(Claim).filter(Claim.id == claim_id).first()
        
        if not claim:
            raise ClaimNotFoundException(str(claim_id))
        
        # Run fraud analysis
        fraud_result = self.fraud_service.analyze_claim(claim)
        
        # Update claim with fraud score
        claim.fraud_score = fraud_result.fraud_score
        
        # Update status based on fraud score
        if fraud_result.fraud_score >= 0.7:
            claim.status = ClaimStatus.MANUAL_REVIEW_REQUIRED.value
            # Increment prior_fraud_flags for high-risk claims
            self._update_user_profile_on_fraud(claim.user_id)
        else:
            claim.status = ClaimStatus.FRAUD_ANALYZED.value
        
        self.db.commit()
        self.db.refresh(claim)
        
        return claim
    
    def _update_user_profile_on_claim(self, user_id) -> None:
        """
        Increment recent_claim_count on claim creation.
        Creates a default profile if one does not exist.
        """
        profile = (
            self.db.query(UserFraudProfile)
            .filter(UserFraudProfile.user_id == user_id)
            .first()
        )
        if profile is None:
            profile = UserFraudProfile(
                user_id=user_id,
                recent_claim_count=1,
                prior_fraud_flags=0,
                last_updated=datetime.utcnow(),
            )
            self.db.add(profile)
        else:
            profile.recent_claim_count += 1
            profile.last_updated = datetime.utcnow()
        self.db.commit()
    
    def _update_user_profile_on_fraud(self, user_id) -> None:
        """
        Increment prior_fraud_flags when fraud score >= threshold.
        Creates a default profile if one does not exist.
        """
        profile = (
            self.db.query(UserFraudProfile)
            .filter(UserFraudProfile.user_id == user_id)
            .first()
        )
        if profile is None:
            profile = UserFraudProfile(
                user_id=user_id,
                recent_claim_count=0,
                prior_fraud_flags=1,
                last_updated=datetime.utcnow(),
            )
            self.db.add(profile)
        else:
            profile.prior_fraud_flags += 1
            profile.last_updated = datetime.utcnow()
        self.db.commit()

    def _record_confirmed_fraud(self, user_id) -> None:
        """
        Increment ``confirmed_fraud_count`` when an admin REJECTS a claim with
        a high fraud score.  This feeds back into the Layer 2 behavioral model
        so that prior confirmed fraud events are counted accurately.
        """
        profile = (
            self.db.query(UserFraudProfile)
            .filter(UserFraudProfile.user_id == user_id)
            .first()
        )
        if profile is None:
            profile = UserFraudProfile(
                user_id=user_id,
                recent_claim_count=0,
                prior_fraud_flags=1,
                confirmed_fraud_count=1,
                last_updated=datetime.utcnow(),
            )
            self.db.add(profile)
        else:
            profile.confirmed_fraud_count = (profile.confirmed_fraud_count or 0) + 1
            profile.prior_fraud_flags += 1   # also bump soft flag count
            profile.last_updated = datetime.utcnow()
        self.db.commit()
    
    def _can_access_claim(self, claim: Claim, user: User) -> bool:
        """
        Check if user can access claim
        
        Args:
            claim: Claim object
            user: User object
        
        Returns:
            bool: True if authorized
        """
        # Customer can only access own claims
        if user.role == "CUSTOMER":
            return str(claim.user_id) == str(user.id)
        
        # Admin and Auditor can access all claims
        if user.role in ["INSURER_ADMIN", "AUDITOR"]:
            return True
        
        # Provider can access claims with QR authorization
        # (handled separately in QR validation)
        
        return False