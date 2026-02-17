"""
Settlement Service
Tracks claim settlements and payment status.
NO bank credentials stored — only references.
"""
import logging
import uuid
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.settlement import Settlement
from app.models.claim import Claim
from app.core.constants import ClaimStatus, AuditAction
from app.core.exceptions import ClaimNotFoundException, InvalidClaimStatusException
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class SettlementService:
    """
    Settlement management service.

    CRITICAL RULES:
    1. Only APPROVED claims can be settled
    2. No bank credentials stored — external payment gateway handles that
    3. All settlement actions are audit-logged
    4. Settlement creates an immutable record
    """

    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    def initiate_settlement(
        self,
        claim_id: uuid.UUID,
        amount: float,
        admin_id: uuid.UUID,
        external_reference: Optional[str] = None,
    ) -> Settlement:
        """
        Initiate settlement for an approved claim.

        Args:
            claim_id: Claim UUID
            amount: Settlement amount (may differ from claim amount after deductions)
            admin_id: Admin initiating settlement
            external_reference: Reference ID from payment gateway (optional)

        Returns:
            Settlement record

        Raises:
            ClaimNotFoundException
            InvalidClaimStatusException: If claim is not APPROVED
        """
        claim = self.db.query(Claim).filter(Claim.id == claim_id).first()
        if not claim:
            raise ClaimNotFoundException(str(claim_id))

        if claim.status != ClaimStatus.APPROVED.value:
            raise InvalidClaimStatusException(
                current_status=claim.status,
                required_status=ClaimStatus.APPROVED.value
            )

        # Generate reference if not provided by payment gateway
        reference_id = external_reference or f"INS-{secrets.token_hex(8).upper()}"

        settlement = Settlement(
            id=uuid.uuid4(),
            claim_id=claim_id,
            settlement_reference_id=reference_id,
            amount=amount,
            status="PENDING",
        )
        self.db.add(settlement)

        # Update claim status
        claim.status = ClaimStatus.SETTLED.value
        self.db.commit()
        self.db.refresh(settlement)

        # Audit log
        self.audit_service.log_action(
            actor_id=admin_id,
            action_type=AuditAction.SETTLEMENT_INITIATED,
            entity_type="SETTLEMENT",
            entity_id=settlement.id,
            metadata={
                "claim_id": str(claim_id),
                "amount": amount,
                "reference_id": reference_id,
            }
        )

        logger.info(
            f"Settlement initiated: claim={claim_id} amount={amount} ref={reference_id}"
        )

        return settlement

    def update_settlement_status(
        self,
        settlement_id: uuid.UUID,
        new_status: str,
        admin_id: uuid.UUID,
    ) -> Settlement:
        """
        Update settlement status (called by payment gateway webhook or admin).

        Args:
            settlement_id: Settlement UUID
            new_status: PROCESSING, COMPLETED, or FAILED
            admin_id: Actor UUID

        Returns:
            Updated Settlement
        """
        valid_statuses = {"PROCESSING", "COMPLETED", "FAILED"}
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}. Must be one of {valid_statuses}")

        settlement = self.db.query(Settlement).filter(Settlement.id == settlement_id).first()
        if not settlement:
            raise ValueError(f"Settlement {settlement_id} not found")

        old_status = settlement.status
        settlement.status = new_status
        self.db.commit()
        self.db.refresh(settlement)

        logger.info(
            f"Settlement updated: id={settlement_id} "
            f"{old_status} → {new_status}"
        )

        return settlement

    def get_claim_settlement(self, claim_id: uuid.UUID) -> Optional[Settlement]:
        """Get the most recent settlement for a claim"""
        return (
            self.db.query(Settlement)
            .filter(Settlement.claim_id == claim_id)
            .order_by(Settlement.created_at.desc())
            .first()
        )