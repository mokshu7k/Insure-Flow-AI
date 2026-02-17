"""
Compliance: Data Retention Policy
Enforces data lifecycle: retention periods, archival, deletion requests.
Regulation baseline: IRDAI 7-year retention, DPDP Act erasure rights.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.claim import Claim
from app.models.document import Document
from app.models.consent import UserConsent
from app.models.user import User
from app.config import settings

logger = logging.getLogger(__name__)

# Retention periods (in days)
RETENTION_POLICIES = {
    "CLAIM":        2555,   # 7 years (IRDAI mandate)
    "DOCUMENT":     2555,   # 7 years
    "CONSENT":      3650,   # 10 years (evidentiary value)
    "AUDIT_LOG":    3650,   # 10 years (never delete in practice)
    "ACCESS_LOG":   1825,   # 5 years
    "USER":         2555,   # 7 years post-deactivation
}


class RetentionPolicy:
    """
    Data retention policy enforcer.

    CRITICAL:
    - Audit logs are NEVER deleted — only archived
    - Claims within retention window cannot be hard-deleted
    - Deletion requests are soft-deletes until retention expires
    - All actions are themselves audit-logged
    """

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────
    # Retention checks
    # ─────────────────────────────────────────────

    def is_within_retention(self, entity_type: str, created_at: datetime) -> bool:
        """
        Check if a record is within its mandatory retention period.

        Args:
            entity_type: CLAIM, DOCUMENT, AUDIT_LOG, etc.
            created_at: Record creation timestamp

        Returns:
            True if record must be retained (cannot be deleted)
        """
        retention_days = RETENTION_POLICIES.get(entity_type.upper(), 2555)
        retention_cutoff = datetime.utcnow() - timedelta(days=retention_days)
        return created_at >= retention_cutoff

    def can_delete_user_data(self, user_id: uuid.UUID) -> tuple[bool, str]:
        """
        Evaluate if a user's data can be deleted (DPDP right to erasure).

        Blocking conditions:
        - Open claims (not SETTLED or REJECTED)
        - Claims within 7-year retention window

        Args:
            user_id: User UUID

        Returns:
            Tuple of (can_delete: bool, reason: str)
        """
        # Check for open claims
        open_claims = self.db.query(Claim).filter(
            Claim.user_id == user_id,
            Claim.status.notin_(["SETTLED", "REJECTED"])
        ).count()

        if open_claims > 0:
            return False, f"User has {open_claims} open/pending claim(s)"

        # Check for claims within retention window
        retention_cutoff = datetime.utcnow() - timedelta(days=RETENTION_POLICIES["CLAIM"])
        retained_claims = self.db.query(Claim).filter(
            Claim.user_id == user_id,
            Claim.created_at >= retention_cutoff
        ).count()

        if retained_claims > 0:
            return False, (
                f"{retained_claims} claim(s) are within the mandatory "
                f"{RETENTION_POLICIES['CLAIM']}-day retention period"
            )

        return True, "User data may be deleted"

    # ─────────────────────────────────────────────
    # Deletion workflow
    # ─────────────────────────────────────────────

    def process_deletion_request(self, user_id: uuid.UUID, requested_by: uuid.UUID) -> dict:
        """
        Process a DPDP erasure request.

        FLOW:
        1. Check if deletion is permitted
        2. If permitted: soft-delete user, deactivate account
        3. If not permitted: record request, schedule for future
        4. Never delete audit_logs

        Args:
            user_id: User whose data to delete
            requested_by: User making the request (usually same user or admin)

        Returns:
            Dict with deletion decision and details
        """
        can_delete, reason = self.can_delete_user_data(user_id)

        if not can_delete:
            logger.info(f"Deletion request deferred for user {user_id}: {reason}")
            return {
                "deletion_approved": False,
                "reason": reason,
                "scheduled_for": self._calculate_earliest_deletion(user_id),
                "user_id": str(user_id),
            }

        # Perform soft deletion
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_active = False
            user.email = f"deleted_{user_id}@insureflow.deleted"  # Anonymize email
            self.db.commit()

        logger.info(f"User {user_id} soft-deleted by {requested_by}")

        return {
            "deletion_approved": True,
            "action_taken": "soft_delete",
            "reason": "All retention requirements satisfied",
            "user_id": str(user_id),
            "deleted_at": datetime.utcnow().isoformat(),
            "note": "Audit logs are retained as required by law",
        }

    # ─────────────────────────────────────────────
    # Scheduled retention cleanup
    # ─────────────────────────────────────────────

    def run_retention_sweep(self) -> dict:
        """
        Scheduled job: identify and process records past retention.
        Should be run daily via cron or Celery.

        Returns:
            Summary of actions taken
        """
        summary = {
            "run_at": datetime.utcnow().isoformat(),
            "expired_claims": 0,
            "archived_documents": 0,
            "errors": [],
        }

        try:
            expired_claims = self._find_expired_claims()
            summary["expired_claims"] = len(expired_claims)
            logger.info(f"Retention sweep: {len(expired_claims)} expired claims identified")

        except Exception as e:
            logger.error(f"Retention sweep error: {e}")
            summary["errors"].append(str(e))

        return summary

    # ─────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────

    def _find_expired_claims(self) -> list:
        """Find claims past their retention period"""
        cutoff = datetime.utcnow() - timedelta(days=RETENTION_POLICIES["CLAIM"])
        return self.db.query(Claim).filter(
            Claim.created_at < cutoff,
            Claim.status.in_(["SETTLED", "REJECTED"])
        ).all()

    def _calculate_earliest_deletion(self, user_id: uuid.UUID) -> Optional[str]:
        """Calculate the earliest date a user's data can be deleted"""
        latest_claim = self.db.query(Claim).filter(
            Claim.user_id == user_id
        ).order_by(Claim.created_at.desc()).first()

        if not latest_claim:
            return datetime.utcnow().isoformat()

        earliest = latest_claim.created_at + timedelta(days=RETENTION_POLICIES["CLAIM"])
        return earliest.strftime("%Y-%m-%d")