"""
QR Token Signer
Cryptographic signing and verification for QR tokens
"""
import hmac
import hashlib
import json
import base64
from datetime import datetime, timedelta
from typing import Dict, Any

from app.config import settings


class QRSigner:
    """
    QR token signing and verification
    Uses HMAC-SHA256 for token integrity
    """
    
    def __init__(self):
        self.secret_key = settings.QR_SECRET_KEY.encode()
    
    def sign(self, payload: Dict[str, Any], expiry_minutes: int) -> str:
        """
        Sign payload and create token
        
        Args:
            payload: Data to sign
            expiry_minutes: Token validity period
        
        Returns:
            Signed token string
        """
        # Add expiry to payload
        expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)
        payload["exp"] = expires_at.isoformat()
        
        # Encode payload
        payload_json = json.dumps(payload, sort_keys=True)
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()
        
        # Generate HMAC signature
        signature = hmac.new(
            self.secret_key,
            payload_b64.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Combine payload and signature
        token = f"{payload_b64}.{signature}"
        
        return token
    
    def verify(self, token: str) -> Dict[str, Any]:
        """
        Verify token signature and extract payload
        
        Args:
            token: Signed token
        
        Returns:
            Decoded payload
        
        Raises:
            ValueError: If token is invalid or expired
        """
        # Split token
        try:
            payload_b64, signature = token.split(".")
        except ValueError:
            raise ValueError("Invalid token format")
        
        # Verify signature
        expected_signature = hmac.new(
            self.secret_key,
            payload_b64.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("Invalid token signature")
        
        # Decode payload
        try:
            payload_json = base64.urlsafe_b64decode(payload_b64.encode()).decode()
            payload = json.loads(payload_json)
        except Exception:
            raise ValueError("Invalid token payload")
        
        # Check expiry
        exp_str = payload.get("exp")
        if not exp_str:
            raise ValueError("Token missing expiry")
        
        exp_time = datetime.fromisoformat(exp_str)
        if datetime.utcnow() > exp_time:
            raise ValueError("Token has expired")
        
        return payload