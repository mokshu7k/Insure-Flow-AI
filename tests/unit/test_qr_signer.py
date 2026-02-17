"""
Unit Tests: QR Token Signer
Uses a fixed test secret key, no patching required.
"""
import time
import pytest
from unittest.mock import patch
from app.utils.qr_signer import QRSigner


@pytest.fixture
def signer():
    with patch("app.utils.qr_signer.settings") as m:
        m.QR_SECRET_KEY = "test-secret-key-exactly-32-chars!!"
        yield QRSigner()


class TestQRSigning:
    def test_sign_returns_dot_separated_string(self, signer):
        token = signer.sign({"claim_id": "abc"}, expiry_minutes=30)
        assert isinstance(token, str)
        assert token.count(".") == 1

    def test_verify_valid_token(self, signer):
        payload = {"claim_id": "c1", "provider_id": "p1", "approved_limit": 50_000.0}
        token = signer.sign(payload, expiry_minutes=30)
        decoded = signer.verify(token)
        assert decoded["claim_id"] == "c1"
        assert decoded["approved_limit"] == 50_000.0

    def test_tampered_signature_fails(self, signer):
        token = signer.sign({"x": "y"}, expiry_minutes=30)
        parts = token.split(".")
        bad = parts[0] + ".BADSIG" + parts[1]
        with pytest.raises(ValueError):
            signer.verify(bad)

    def test_expired_token_fails(self, signer):
        token = signer.sign({"x": "y"}, expiry_minutes=-1)
        with pytest.raises(ValueError, match="expired"):
            signer.verify(token)

    def test_missing_dot_fails(self, signer):
        with pytest.raises(ValueError):
            signer.verify("nodothere")

    def test_different_payloads_produce_different_tokens(self, signer):
        t1 = signer.sign({"a": "1"}, expiry_minutes=30)
        t2 = signer.sign({"a": "2"}, expiry_minutes=30)
        assert t1 != t2

    def test_exp_field_present_in_decoded(self, signer):
        token = signer.sign({"k": "v"}, expiry_minutes=10)
        decoded = signer.verify(token)
        assert "exp" in decoded