"""
Claim Context Builder
Constructs the enriched claim_context dict required by the fraud engine.
All historical data comes from the materialized UserFraudProfile table.
"""
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.claim import Claim
from app.models.user_fraud_profile import UserFraudProfile


class ClaimContextBuilder:
    """
    Builds a fully enriched claim context dict for the fraud engine.

    Responsibilities:
        1. Map core claim fields into the context dict.
        2. Fetch (or auto-create) the user's materialized fraud profile.
        3. Compute days_to_policy_expiry (stub -- requires policy table).

    The fraud engine MUST receive all fields. Layer 2 raises ValueError
    if any required field is missing.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def build(self, claim: Claim) -> dict:
        """
        Build the complete claim context dict.

        Args:
            claim: The Claim ORM object to analyse.

        Returns:
            Dict with all fields required by the fraud engine layers.
        """
        profile = self._get_or_create_profile(claim.user_id)

        return {
            "claim_id": str(claim.id),
            "policy_number": claim.policy_number,
            "claim_type": claim.claim_type,
            "claim_amount": claim.claim_amount,
            "user_id": str(claim.user_id),
            "recent_claim_count": profile.recent_claim_count,
            "prior_fraud_flags": profile.prior_fraud_flags,
            "days_to_policy_expiry": self._days_to_policy_expiry(claim.policy_number),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_or_create_profile(self, user_id) -> UserFraudProfile:
        """Fetch the profile row; create a default one if missing."""
        profile = (
            self.db.query(UserFraudProfile)
            .filter(UserFraudProfile.user_id == user_id)
            .first()
        )
        if profile is None:
            profile = UserFraudProfile(
                user_id=user_id,
                recent_claim_count=0,
                prior_fraud_flags=0,
                last_updated=datetime.utcnow(),
            )
            self.db.add(profile)
            self.db.flush()  # make visible in current transaction
        return profile

    @staticmethod
    def _days_to_policy_expiry(policy_number: str) -> int:
        """
        Compute days remaining until the policy expires.

        NOTE: This is a stub. In production, query the policy table
        using the policy_number to get the actual expiry date.
        Returns a safe default (365) until the policy table is
        integrated.
        """
        # TODO: Replace with actual policy expiry lookup
        # e.g.:
        #   policy = self.db.query(Policy).filter(
        #       Policy.policy_number == policy_number
        #   ).first()
        #   if policy and policy.expiry_date:
        #       return (policy.expiry_date - date.today()).days
        return 365
