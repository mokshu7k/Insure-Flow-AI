"""
Compliance: Human Override Enforcement
CRITICAL compliance module — ensures AI never makes final decisions.
All high-fraud-score claims require a named human adjuster to act.
"""
import logging
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.audit import AuditLog
from app.core.constants import ClaimStatus, AuditAction
from app.core.exceptions import InvalidClaimStatusException

logger = logging.getLogger(__name__)

# Claims above this score CANNOT be approved/rejected by any automated path
HUMAN_REVIEW_THRESHOLD = 0.70

# Status transitions that require a human actor
HUMAN_REQUIRED_TRANSITIONS = {
    "APPROVED",
    "REJECTED",
}


class HumanOverrideEnforcer:
    """
    Human-in-the-loop enforcement layer.

    ARCHITECTURE PRINCIPLE:
    AI systems produce SCORES and FLAGS.
    AI systems NEVER produce APPROVED or REJECTED statuses.
    Only authenticated human admins can move a claim to APPROVED/REJECTED.

    This class is the single enforcement point for that rule.
    It is called from claim_service.py BEFORE any status update.

    CRITICAL:
    - Bypassing this class = compliance violation
    - All override decisions are logged with actor + reasoning
    - Override log cannot be modified after creation (audit table rules)
    """

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────
    # Enforcement
    # ─────────────────────────────────────────────

    def enforce_human_required(
        self,
        claim: Claim,
        new_status: str,
        actor_id: uuid.UUID,
        actor_role: str,
    ) -> None:
        """
        Gate check for status transitions requiring a human.

        Args:
            claim: The claim being updated
            new_status: Target status (APPROVED, REJECTED, etc.)
            actor_id: UUID of the user attempting the transition
            actor_role: Role of the actor

        Raises:
            InvalidClaimStatusException: If transition is not permitted
        """
        if new_status not in HUMAN_REQUIRED_TRANSITIONS:
            return  # Not a protected transition

        # Only INSURER_ADMIN can approve/reject
        if actor_role != "INSURER_ADMIN":
            raise InvalidClaimStatusException(
                current_status=claim.status,
                required_status=f"INSURER_ADMIN role required for {new_status}"
            )

        # If fraud score is high, claim MUST be in MANUAL_REVIEW_REQUIRED first
        if (
            claim.fraud_score is not None and
            claim.fraud_score >= HUMAN_REVIEW_THRESHOLD and
            claim.status != ClaimStatus.MANUAL_REVIEW_REQUIRED.value
        ):
            raise InvalidClaimStatusException(
                current_status=claim.status,
                required_status=ClaimStatus.MANUAL_REVIEW_REQUIRED.value
            )

        logger.info(
            f"Human override check passed: claim={claim.id} "
            f"new_status={new_status} actor={actor_id} role={actor_role}"
        )

    def record_human_decision(
        self,
        claim: Claim,
        new_status: str,
        actor_id: uuid.UUID,
        reason: str,
        override_fraud_score: bool = False,
    ) -> AuditLog:
        """
        Record a human override decision in the immutable audit log.

        This is the compliance record that proves a human — not a machine —
        made the final claim decision.

        Args:
            claim: Claim being decided
            new_status: Decision (APPROVED or REJECTED)
            actor_id: Human adjuster's UUID
            reason: Written justification (mandatory for compliance)
            override_fraud_score: True if admin is overriding a high fraud score

        Returns:
            AuditLog entry
        """
        metadata = {
            "previous_status": claim.status,
            "new_status": new_status,
            "fraud_score": claim.fraud_score,
            "override_fraud_score": override_fraud_score,
            "reason": reason,
            "decision_timestamp": datetime.utcnow().isoformat(),
            "claim_amount": claim.claim_amount,
            "policy_number": claim.policy_number,
        }

        if override_fraud_score and claim.fraud_score:
            metadata["fraud_override_justification"] = reason

        audit_entry = AuditLog(
            id=uuid.uuid4(),
            actor_id=actor_id,
            action_type=AuditAction.MANUAL_OVERRIDE.value,
            entity_type="CLAIM",
            entity_id=claim.id,
            metadata_json=metadata,
            timestamp=datetime.utcnow(),
        )

        self.db.add(audit_entry)
        self.db.commit()

        logger.info(
            f"HUMAN_DECISION: claim={claim.id} decision={new_status} "
            f"actor={actor_id} fraud_score={claim.fraud_score} "
            f"override={override_fraud_score}"
        )

        return audit_entry

    def check_requires_review(self, claim: Claim) -> tuple[bool, str]:
        """
        Determine if a claim requires manual human review.

        Args:
            claim: Claim to check

        Returns:
            Tuple of (requires_review: bool, reason: str)
        """
        reasons = []

        if claim.fraud_score is None:
            reasons.append("Fraud analysis not yet run")

        elif claim.fraud_score >= HUMAN_REVIEW_THRESHOLD:
            reasons.append(
                f"Fraud score {claim.fraud_score:.2f} exceeds threshold "
                f"{HUMAN_REVIEW_THRESHOLD}"
            )

        if claim.claim_amount > 500000:
            reasons.append("High-value claim requires senior adjuster review")

        if reasons:
            return True, "; ".join(reasons)

        return False, "Claim may be processed without mandatory human review"

    def get_pending_reviews(self, limit: int = 50) -> list:
        """
        Get all claims pending human review.

        Args:
            limit: Max results

        Returns:
            List of Claim objects in MANUAL_REVIEW_REQUIRED status
        """
        return (
            self.db.query(Claim)
            .filter(Claim.status == ClaimStatus.MANUAL_REVIEW_REQUIRED.value)
            .order_by(Claim.fraud_score.desc())  # Highest fraud score first
            .limit(limit)
            .all()
        )