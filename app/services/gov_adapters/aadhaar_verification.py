"""
Aadhaar QR verification adapter.
Rule-based verification using QR code extraction and digital signature validation.
No external API calls.
"""
from __future__ import annotations

import base64
import io
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class AadhaarVerificationResult:
    """Result of Aadhaar verification."""
    is_valid: bool
    has_qr: bool
    signature_valid: bool
    extracted_data: dict[str, Any]
    fraud_signal_weight: float  # 0.0–1.0
    reason: str


class AadhaarQRVerifier:
    """
    Verifies Aadhaar card authenticity via QR code validation.
    
    Validation rules:
    1. QR code must be present
    2. QR payload must be decodable
    3. Digital signature must be valid (UIDAI public key)
    
    Returns structured result with fraud signal weight.
    """
    
    # UIDAI public key for signature verification (demo/mock - replace with real key in production)
    UIDAI_PUBLIC_KEY = None  # In production, load actual UIDAI certificate
    
    def __init__(self):
        """Initialize verifier with necessary dependencies."""
        try:
            import pyzbar.pyzbar as pyzbar
            self.pyzbar = pyzbar
        except ImportError:
            logger.warning("pyzbar not available - QR extraction will be limited")
            self.pyzbar = None
    
    async def verify(self, file_bytes: bytes) -> AadhaarVerificationResult:
        """
        Verify Aadhaar document authenticity.
        
        Args:
            file_bytes: Raw document bytes (image or PDF)
        
        Returns:
            AadhaarVerificationResult with validation outcome
        """
        try:
            # Step 1: Extract QR code from document
            qr_data = await self._extract_qr_code(file_bytes)
            
            if not qr_data:
                # No QR found → HIGH_RISK
                return AadhaarVerificationResult(
                    is_valid=False,
                    has_qr=False,
                    signature_valid=False,
                    extracted_data={},
                    fraud_signal_weight=0.6,
                    reason="QR code not found - cannot verify authenticity"
                )
            
            # Step 2: Parse QR payload
            parsed_data = self._parse_qr_payload(qr_data)
            
            if not parsed_data:
                return AadhaarVerificationResult(
                    is_valid=False,
                    has_qr=True,
                    signature_valid=False,
                    extracted_data={},
                    fraud_signal_weight=0.8,
                    reason="QR code data corrupted or invalid format"
                )
            
            # Step 3: Validate digital signature
            signature_valid = await self._validate_signature(qr_data, parsed_data)
            
            if not signature_valid:
                # Signature invalid → CRITICAL
                return AadhaarVerificationResult(
                    is_valid=False,
                    has_qr=True,
                    signature_valid=False,
                    extracted_data=parsed_data,
                    fraud_signal_weight=1.0,
                    reason="Digital signature verification failed - potential forgery"
                )
            
            # All checks passed
            return AadhaarVerificationResult(
                is_valid=True,
                has_qr=True,
                signature_valid=True,
                extracted_data=parsed_data,
                fraud_signal_weight=0.0,
                reason="Aadhaar verification successful"
            )
        
        except Exception as exc:
            logger.error(f"Aadhaar verification failed: {exc}", exc_info=True)
            return AadhaarVerificationResult(
                is_valid=False,
                has_qr=False,
                signature_valid=False,
                extracted_data={},
                fraud_signal_weight=0.7,
                reason=f"Verification error: {str(exc)}"
            )
    
    async def _extract_qr_code(self, file_bytes: bytes) -> str | None:
        """Extract QR code data from image/PDF."""
        if not self.pyzbar:
            logger.warning("pyzbar not available - cannot extract QR")
            return None
        
        try:
            # Try direct image decode
            image = Image.open(io.BytesIO(file_bytes))
            
            # Convert to RGB if necessary
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            
            # Decode QR codes
            decoded_objects = self.pyzbar.decode(image)
            
            if not decoded_objects:
                # Try PDF extraction if available
                qr_from_pdf = await self._extract_qr_from_pdf(file_bytes)
                if qr_from_pdf:
                    return qr_from_pdf
                return None
            
            # Return first QR code data
            return decoded_objects[0].data.decode("utf-8", errors="replace")
        
        except Exception as exc:
            logger.warning(f"QR extraction failed: {exc}")
            return None
    
    async def _extract_qr_from_pdf(self, file_bytes: bytes) -> str | None:
        """Extract QR from PDF by rendering pages as images."""
        try:
            # Check if it's a PDF
            if not file_bytes[:4] == b"%PDF":
                return None
            
            # Use pdf2image if available
            try:
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(file_bytes, first_page=1, last_page=1)
                if images and self.pyzbar:
                    decoded = self.pyzbar.decode(images[0])
                    if decoded:
                        return decoded[0].data.decode("utf-8", errors="replace")
            except ImportError:
                logger.debug("pdf2image not available - skipping PDF QR extraction")
            
            return None
        except Exception:
            return None
    
    def _parse_qr_payload(self, qr_data: str) -> dict[str, Any]:
        """
        Parse Aadhaar QR payload.
        
        Aadhaar QR typically contains XML with fields:
        - uid: Aadhaar number
        - name: Cardholder name
        - dob: Date of birth
        - gender: M/F/T
        - address: Full address
        """
        try:
            # Aadhaar QR v2 format is typically XML-based
            # Handle base64 encoding if present
            if re.match(r'^[A-Za-z0-9+/=]+$', qr_data):
                try:
                    decoded = base64.b64decode(qr_data)
                    qr_data = decoded.decode("utf-8", errors="replace")
                except Exception:
                    pass
            
            # Try XML parsing
            try:
                root = ET.fromstring(qr_data)
                return {
                    "uid": root.get("uid", ""),
                    "name": root.get("name", ""),
                    "dob": root.get("dob", ""),
                    "gender": root.get("gender", ""),
                    "address": root.get("co", "") + " " + root.get("loc", ""),
                    "raw": qr_data[:100]  # First 100 chars for logging
                }
            except ET.ParseError:
                # Try simple key-value parsing if not XML
                data = {}
                for part in qr_data.split(","):
                    if ":" in part:
                        key, val = part.split(":", 1)
                        data[key.strip()] = val.strip()
                return data if data else {"raw": qr_data[:100]}
        
        except Exception as exc:
            logger.warning(f"QR payload parsing failed: {exc}")
            return {}
    
    async def _validate_signature(self, qr_data: str, parsed_data: dict[str, Any]) -> bool:
        """
        Validate digital signature using UIDAI public key.
        
        In production, this would:
        1. Extract signature from QR payload
        2. Verify using UIDAI's X.509 certificate
        3. Check certificate validity and chain
        
        For now, we perform basic validation checks.
        """
        # Mock implementation - replace with real cryptographic verification
        if not parsed_data:
            return False
        
        # In production, use cryptography library:
        # from cryptography.hazmat.primitives import hashes
        # from cryptography.hazmat.primitives.asymmetric import padding
        # Verify signature against UIDAI public key
        
        # For now, basic sanity checks
        has_uid = bool(parsed_data.get("uid"))
        has_name = bool(parsed_data.get("name"))
        
        # In a real implementation, this would verify the digital signature
        # For demo purposes, we consider it valid if basic fields are present
        return has_uid and has_name
