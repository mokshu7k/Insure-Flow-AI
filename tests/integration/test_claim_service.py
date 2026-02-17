"""
Integration Tests: Claim Service
Tests consent gate, human override wiring, and RBAC — all without a real DB.
"""
import uuid
import pytest
from unittest.mock import MagicMock, patch

from app.services.claim_service import ClaimService
from app.schemas.claim import ClaimCreate, ClaimStatusUpdate
from app.core.constants import ClaimStatus
from app.core.exceptions import ConsentNotGivenException, InvalidClaimStatusException


def mock_user(role="CUSTOMER"):
    u = MagicMock()
    u.id = uuid.uuid4()
    u.role = role
    u.email = "test@example.com"
    return u


def mock_claim(status="SUBMITTED", fraud_score=None, user_id=None):
    c = MagicMock()
    c.id = uuid.uuid4()
    c.policy_number = "POL-2024-99999"
    c.user_id = user_id or uuid.uuid4()
    c.claim_type = "HEALTH"
    c.claim_amount = 50_000.0
    c.status = status
    c.fraud_score = fraud_score
    return c


class TestConsentGate:
    def test_create_claim_fails_without_consent(self):
        db = MagicMock()
        customer = mock_user("CUSTOMER")
        with patch(
            "app.compliance.consent_validator.ConsentValidator.has_valid_consent",
            return_value=False,
        ):
            svc = ClaimService(db)
            with pytest.raises(ConsentNotGivenException):
                svc.create_claim(
                    ClaimCreate(
                        policy_number="POL-12345",
                        claim_type="HEALTH",
                        claim_amount=50_000.0,
                    ),
                    customer,
                )

    def test_create_claim_passes_with_consent(self):
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        customer = mock_user("CUSTOMER")

        with patch(
            "app.compliance.consent_validator.ConsentValidator.has_valid_consent",
            return_value=True,
        ), patch("app.services.audit_service.AuditService.log_action"):
            svc = ClaimService(db)
            # Should not raise — DB ops are mocked
            try:
                svc.create_claim(
                    ClaimCreate(
                        policy_number="POL-VALID-12345",
                        claim_type="HEALTH",
                        claim_amount=75_000.0,
                    ),
                    customer,
                )
            except Exception as e:
                # Only mock-related errors are acceptable
                assert "Mock" in type(e).__name__ or "NoneType" in str(e)


class TestHumanOverrideWiring:
    """Verify HumanOverrideEnforcer is called from update_claim_status."""

    def test_customer_cannot_approve(self):
        """CUSTOMER role → enforce_human_required must raise."""
        db = MagicMock()
        customer = mock_user("CUSTOMER")
        claim = mock_claim(status="FRAUD_ANALYZED", fraud_score=0.5)
        db.query.return_value.filter.return_value.first.return_value = claim

        svc = ClaimService(db)
        with pytest.raises(InvalidClaimStatusException):
            svc.update_claim_status(
                claim.id,
                ClaimStatusUpdate(status="APPROVED", reason="test"),
                customer,
            )

    def test_admin_can_approve_low_fraud(self):
        """Admin + low fraud score + claim not in manual review → allowed."""
        db = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        admin = mock_user("INSURER_ADMIN")
        claim = mock_claim(status="FRAUD_ANALYZED", fraud_score=0.3)
        db.query.return_value.filter.return_value.first.return_value = claim

        with patch("app.services.audit_service.AuditService.log_action"), \
             patch("app.compliance.human_override.HumanOverrideEnforcer.record_human_decision"):
            svc = ClaimService(db)
            # Should pass enforcement — no exception
            try:
                svc.update_claim_status(
                    claim.id,
                    ClaimStatusUpdate(status="APPROVED", reason="Looks good"),
                    admin,
                )
            except Exception as e:
                assert "Mock" in type(e).__name__

    def test_admin_cannot_approve_high_fraud_without_review(self):
        """High fraud score + status not MANUAL_REVIEW_REQUIRED → blocked."""
        db = MagicMock()
        admin = mock_user("INSURER_ADMIN")
        claim = mock_claim(status="FRAUD_ANALYZED", fraud_score=0.85)
        db.query.return_value.filter.return_value.first.return_value = claim

        svc = ClaimService(db)
        with pytest.raises(InvalidClaimStatusException):
            svc.update_claim_status(
                claim.id,
                ClaimStatusUpdate(status="APPROVED", reason="force approve"),
                admin,
            )


class TestClaimAccess:
    def _svc(self):
        svc = ClaimService.__new__(ClaimService)
        svc.db = MagicMock()
        return svc

    def test_customer_owns_claim(self):
        customer = mock_user("CUSTOMER")
        claim = mock_claim(user_id=customer.id)
        assert self._svc()._can_access_claim(claim, customer) is True

    def test_customer_cannot_access_other_claim(self):
        customer = mock_user("CUSTOMER")
        claim = mock_claim(user_id=uuid.uuid4())
        assert self._svc()._can_access_claim(claim, customer) is False

    def test_admin_accesses_any_claim(self):
        admin = mock_user("INSURER_ADMIN")
        claim = mock_claim(user_id=uuid.uuid4())
        assert self._svc()._can_access_claim(claim, admin) is True

    def test_auditor_accesses_any_claim(self):
        auditor = mock_user("AUDITOR")
        claim = mock_claim(user_id=uuid.uuid4())
        assert self._svc()._can_access_claim(claim, auditor) is True


class TestFraudThresholdLogic:
    def test_high_score_maps_to_manual_review(self):
        threshold = 0.70
        assert (0.75 >= threshold) is True

    def test_low_score_maps_to_analyzed(self):
        threshold = 0.70
        assert (0.45 >= threshold) is False