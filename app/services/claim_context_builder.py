"""
Claim Context Builder
Constructs the enriched claim_context dict required by the fraud engine.
All historical data comes from the materialized UserFraudProfile table and
live DB queries for provider network and document signals.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.document import Document
from app.models.fraud import FraudAssessment
from app.models.user_fraud_profile import UserFraudProfile


class ClaimContextBuilder:
    """
    Builds a fully enriched claim context dict for the fraud engine.

    Responsibilities:
        1. Map core claim fields into the context dict.
        2. Fetch (or auto-create) the user's materialized fraud profile.
        3. Compute days_to_policy_expiry from claim.policy_expiry_date.
        4. Surface last_claim_date from the fraud profile for dormancy detection.
        5. Pre-fetch document list + prior invoice numbers for Layer 4.
        6. Pre-fetch provider network statistics for Layer 5.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def build(self, claim: Claim) -> Dict[str, Any]:
        """
        Build the complete claim context dict.

        Args:
            claim: The Claim ORM object to analyse.

        Returns:
            Dict with all fields required by the fraud engine layers.
        """
        profile = self._get_or_create_profile(claim.user_id)
        documents = self._fetch_documents(claim)
        all_invoice_numbers = self._fetch_prior_invoice_numbers(claim)
        provider_stats = self._fetch_provider_stats(claim)

        return {
            # Core claim fields
            "claim_id":      str(claim.id),
            "policy_number": claim.policy_number,
            "claim_type":    claim.claim_type,
            "claim_amount":  claim.claim_amount,
            "user_id":       str(claim.user_id),
            "claim_date":    claim.created_at.isoformat() if claim.created_at else None,

            # Provider
            "provider_id": str(claim.provider_id) if claim.provider_id else None,

            # ---- Layer 2 fields ----
            "recent_claim_count":    profile.recent_claim_count,
            "prior_fraud_flags":     profile.prior_fraud_flags,
            "days_to_policy_expiry": self._days_to_policy_expiry(claim),
            "last_claim_date": (
                profile.last_claim_date.isoformat()
                if profile.last_claim_date is not None
                else None
            ),
            "total_claim_amount_90d": profile.total_claim_amount_90d or 0.0,

            # ---- Layer 4 fields (document fraud) ----
            # List of dicts with keys: invoice_number, ocr_confidence, document_date, document_type
            "documents":           documents,
            "all_invoice_numbers": all_invoice_numbers,

            # ---- Layer 5 fields (network / provider graph) ----
            "provider_claim_count_30d":      provider_stats["claim_count_30d"],
            "provider_high_risk_count_30d":  provider_stats["high_risk_count_30d"],
            "provider_total_claims":         provider_stats["total_claims"],
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
                confirmed_fraud_count=0,
                last_claim_date=None,
                total_claim_amount_90d=0.0,
                last_updated=datetime.utcnow(),
            )
            self.db.add(profile)
            self.db.flush()  # make visible in current transaction
        return profile

    def _fetch_documents(self, claim: Claim) -> List[Dict[str, Any]]:
        """
        Return the documents attached to this claim as a list of dicts
        suitable for Layer 4 document fraud detection.
        """
        rows = (
            self.db.query(Document)
            .filter(Document.claim_id == claim.id)
            .all()
        )
        results: List[Dict[str, Any]] = []
        for doc in rows:
            ocr: Dict[str, Any] = doc.ocr_extracted_json or {}
            results.append({
                "document_type":   doc.document_type,
                "invoice_number":  ocr.get("invoice_number"),
                "ocr_confidence":  ocr.get("confidence"),        # float 0-1 or None
                "document_date":   ocr.get("document_date"),     # ISO date str or None
            })
        return results

    def _fetch_prior_invoice_numbers(self, claim: Claim) -> List[str]:
        """
        Return all invoice numbers found in documents of OTHER claims
        belonging to the same user (used for duplicate-invoice detection).
        """
        other_docs = (
            self.db.query(Document)
            .join(Claim, Document.claim_id == Claim.id)
            .filter(
                Claim.user_id == claim.user_id,
                Claim.id != claim.id,
            )
            .all()
        )
        invoice_numbers: List[str] = []
        for doc in other_docs:
            ocr: Dict[str, Any] = doc.ocr_extracted_json or {}
            num = ocr.get("invoice_number")
            if num:
                invoice_numbers.append(str(num))
        return invoice_numbers

    def _fetch_provider_stats(self, claim: Claim) -> Dict[str, int]:
        """
        Compute provider-level statistics for Layer 5 network analysis.
        Returns zero-valued dict when no provider is attached.
        """
        empty: Dict[str, int] = {
            "claim_count_30d": 0,
            "high_risk_count_30d": 0,
            "total_claims": 0,
        }
        if not claim.provider_id:
            return empty

        cutoff_30d = datetime.now(tz=timezone.utc) - timedelta(days=30)

        total_claims: int = (
            self.db.query(Claim)
            .filter(Claim.provider_id == claim.provider_id)
            .count()
        )

        claims_30d = (
            self.db.query(Claim)
            .filter(
                Claim.provider_id == claim.provider_id,
                Claim.created_at >= cutoff_30d,
            )
            .all()
        )
        claim_count_30d = len(claims_30d)
        claim_ids_30d = [c.id for c in claims_30d]

        high_risk_count_30d: int = 0
        if claim_ids_30d:
            HIGH_RISK_THRESHOLD = 0.70
            high_risk_count_30d = (
                self.db.query(FraudAssessment)
                .filter(
                    FraudAssessment.claim_id.in_(claim_ids_30d),
                    FraudAssessment.fraud_score >= HIGH_RISK_THRESHOLD,
                )
                .count()
            )

        return {
            "claim_count_30d":     claim_count_30d,
            "high_risk_count_30d": high_risk_count_30d,
            "total_claims":        total_claims,
        }

    @staticmethod
    def _days_to_policy_expiry(claim: Claim) -> int:
        """
        Compute calendar days remaining until the policy expires.

        Uses claim.policy_expiry_date when set; falls back to 365 (safe
        default) so the CLAIM_NEAR_POLICY_EXPIRY signal never fires on
        claims whose expiry is unknown.
        """
        if claim.policy_expiry_date is not None:
            today = date.today()
            delta = (claim.policy_expiry_date - today).days
            return delta  # may be negative if already expired
        # Safe default: treat as 1 year remaining
        return 365
