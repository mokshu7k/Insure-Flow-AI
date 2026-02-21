"""
Document Gatekeeper Service

Centralized document validation service that performs:
1. Structural validation (deterministic)
2. LLM-based document type classification
3. Rule-based authenticity validation (Aadhaar + PAN)

Returns structured DocumentDecision objects for consumption by:
- Fraud Engine
- LangGraph AI agent
- Narrative explanation layer

This service is DB-agnostic and route-agnostic - all dependencies are injected.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import mimetypes
from enum import Enum
from functools import partial
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ── Output Models ─────────────────────────────────────────────────────────────
class DocumentDecisionStatus(str, Enum):
    """Document validation status."""
    ACCEPTED = "accepted"
    REJECTED_INVALID = "rejected_invalid"
    FLAGGED_HIGH_RISK = "flagged_high_risk"
    FLAGGED_CRITICAL = "flagged_critical"


class DocumentDecision(BaseModel):
    """
    Structured validation result returned by DocumentGatekeeper.
    
    This object is consumed by fraud engine, AI agents, and narrative layers.
    """
    status: DocumentDecisionStatus
    reason: str
    fraud_signal_weight: float  # 0.0–1.0
    metadata: dict[str, Any]


# ── Document Gatekeeper Service ───────────────────────────────────────────────
class DocumentGatekeeper:
    """
    Centralized document validation service.
    
    Performs multi-stage validation:
    1. Structural validation (hard reject)
    2. LLM classification (type matching)
    3. Authenticity verification (Aadhaar/PAN rules)
    
    Design principles:
    - DB-agnostic (no direct DB access)
    - Route-agnostic (no FastAPI dependencies)
    - Adapter injection for testability
    - Pure validation logic only
    """
    
    # Allowed MIME types
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/tiff",
        "image/bmp",
    }
    
    # Max file size (10 MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    def __init__(
        self,
        aadhaar_verifier=None,
        pan_verifier=None,
        gemini_api_key: str | None = None
    ):
        """
        Initialize document gatekeeper with optional adapters.
        
        Args:
            aadhaar_verifier: Aadhaar verification adapter (injected)
            pan_verifier: PAN verification adapter (injected)
            gemini_api_key: API key for LLM classification
        """
        self.aadhaar_verifier = aadhaar_verifier
        self.pan_verifier = pan_verifier
        self.gemini_api_key = gemini_api_key
        
        # Lazy-load Gemini
        self._gemini_model = None
    
    async def validate_document(
        self,
        file_bytes: bytes,
        filename: str,
        expected_type: str,
        extracted_text: str | None = None,
        holder_name: str | None = None
    ) -> DocumentDecision:
        """
        Main validation entry point.
        
        Executes validation pipeline:
        1. Structural validation
        2. LLM classification
        3. Authenticity verification
        
        Args:
            file_bytes: Raw document bytes
            filename: Original filename
            expected_type: Expected document type (e.g., "aadhaar", "pan", "medical_bill")
            extracted_text: Optional pre-extracted OCR text
            holder_name: Optional holder name for validation
        
        Returns:
            DocumentDecision with status and fraud signal weight
        """
        try:
            # Stage 1: Structural validation (hard reject)
            structural_result = await self._structural_validation(
                file_bytes, filename, extracted_text
            )
            
            if structural_result.status == DocumentDecisionStatus.REJECTED_INVALID:
                return structural_result
            
            # Stage 2: LLM classification (type matching)
            classification_result = await self._classify_document(
                file_bytes, filename, expected_type
            )
            
            if classification_result.status == DocumentDecisionStatus.REJECTED_INVALID:
                return classification_result
            
            # Stage 3: Authenticity verification (Aadhaar/PAN rules)
            authenticity_result = await self._authenticity_verification(
                file_bytes, expected_type, extracted_text, holder_name
            )
            
            return authenticity_result
        
        except Exception as exc:
            logger.error(f"Document validation failed: {exc}", exc_info=True)
            return DocumentDecision(
                status=DocumentDecisionStatus.REJECTED_INVALID,
                reason="Document validation service encountered an error",
                fraud_signal_weight=0.5,
                metadata={"error": str(exc)}
            )
    
    async def _structural_validation(
        self,
        file_bytes: bytes,
        filename: str,
        extracted_text: str | None
    ) -> DocumentDecision:
        """
        Stage 1: Structural validation (deterministic).
        
        Hard rejects for:
        - Invalid MIME type
        - File too large
        - Corrupted file
        - Blank/empty content
        """
        # Check file size
        if len(file_bytes) > self.MAX_FILE_SIZE:
            return DocumentDecision(
                status=DocumentDecisionStatus.REJECTED_INVALID,
                reason="The uploaded document is incorrect",  # User-friendly message
                fraud_signal_weight=0.0,
                metadata={"error": "file_too_large", "size": len(file_bytes)}
            )
        
        # Check MIME type
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            # Try magic bytes detection
            mime_type = self._detect_mime_from_bytes(file_bytes)
        
        if mime_type not in self.ALLOWED_MIME_TYPES:
            return DocumentDecision(
                status=DocumentDecisionStatus.REJECTED_INVALID,
                reason="The uploaded document is incorrect",
                fraud_signal_weight=0.0,
                metadata={"error": "invalid_mime_type", "detected": mime_type}
            )
        
        # Check if file is corrupted (basic magic bytes check)
        if not self._is_valid_file_structure(file_bytes):
            return DocumentDecision(
                status=DocumentDecisionStatus.REJECTED_INVALID,
                reason="The uploaded document is incorrect",
                fraud_signal_weight=0.0,
                metadata={"error": "corrupted_file"}
            )
        
        # Check for empty/blank content
        if extracted_text is not None and len(extracted_text.strip()) == 0:
            return DocumentDecision(
                status=DocumentDecisionStatus.REJECTED_INVALID,
                reason="The uploaded document is incorrect",
                fraud_signal_weight=0.0,
                metadata={"error": "blank_document"}
            )
        
        # Structural validation passed
        return DocumentDecision(
            status=DocumentDecisionStatus.ACCEPTED,
            reason="Structural validation passed",
            fraud_signal_weight=0.0,
            metadata={"stage": "structural", "mime_type": mime_type}
        )
    
    async def _classify_document(
        self,
        file_bytes: bytes,
        filename: str,
        expected_type: str
    ) -> DocumentDecision:
        """
        Stage 2: LLM-based document classification.
        
        Uses Gemini to:
        - Detect actual document type
        - Verify it matches expected type
        - Check relevance to insurance context
        
        Rejects if:
        - Detected type != expected type
        - Document not relevant
        - Low confidence
        """
        try:
            classification = await self._classify_with_gemini(file_bytes, expected_type)
            
            detected_type = classification.get("detected_type", "").lower()
            is_relevant = classification.get("is_relevant", False)
            confidence = classification.get("confidence", 0.0)
            reason_text = classification.get("reason", "")
            
            # Check relevance
            if not is_relevant:
                return DocumentDecision(
                    status=DocumentDecisionStatus.REJECTED_INVALID,
                    reason="The uploaded document is incorrect",
                    fraud_signal_weight=0.0,
                    metadata={
                        "error": "not_relevant",
                        "detected_type": detected_type,
                        "expected": expected_type,
                        "llm_reason": reason_text
                    }
                )
            
            # Check type match (fuzzy matching for common variations)
            if not self._types_match(detected_type, expected_type):
                return DocumentDecision(
                    status=DocumentDecisionStatus.REJECTED_INVALID,
                    reason="The uploaded document is incorrect",
                    fraud_signal_weight=0.0,
                    metadata={
                        "error": "type_mismatch",
                        "detected_type": detected_type,
                        "expected": expected_type,
                        "confidence": confidence
                    }
                )
            
            # Check confidence threshold
            if confidence < 0.5:
                return DocumentDecision(
                    status=DocumentDecisionStatus.FLAGGED_HIGH_RISK,
                    reason=f"Low confidence classification: {reason_text}",
                    fraud_signal_weight=0.4,
                    metadata={
                        "stage": "classification",
                        "detected_type": detected_type,
                        "confidence": confidence
                    }
                )
            
            # Classification passed
            return DocumentDecision(
                status=DocumentDecisionStatus.ACCEPTED,
                reason="Document classification successful",
                fraud_signal_weight=0.0,
                metadata={
                    "stage": "classification",
                    "detected_type": detected_type,
                    "confidence": confidence
                }
            )
        
        except Exception as exc:
            logger.warning(f"LLM classification failed: {exc}")
            # Fail-open: proceed with validation but flag as uncertain
            return DocumentDecision(
                status=DocumentDecisionStatus.ACCEPTED,
                reason="Classification skipped due to service error",
                fraud_signal_weight=0.2,
                metadata={"stage": "classification", "error": str(exc)}
            )
    
    async def _authenticity_verification(
        self,
        file_bytes: bytes,
        document_type: str,
        extracted_text: str | None,
        holder_name: str | None
    ) -> DocumentDecision:
        """
        Stage 3: Rule-based authenticity verification.
        
        Delegates to specialized adapters:
        - Aadhaar: QR code + signature validation
        - PAN: Format + entity type + surname validation
        """
        doc_type_lower = document_type.lower()
        
        # Route to appropriate verifier
        if "aadhaar" in doc_type_lower:
            return await self._verify_aadhaar(file_bytes)
        elif "pan" in doc_type_lower:
            return await self._verify_pan(extracted_text, holder_name)
        else:
            # No specific authenticity rules for this document type
            return DocumentDecision(
                status=DocumentDecisionStatus.ACCEPTED,
                reason="No specific authenticity checks for this document type",
                fraud_signal_weight=0.0,
                metadata={"stage": "authenticity", "type": document_type}
            )
    
    async def _verify_aadhaar(self, file_bytes: bytes) -> DocumentDecision:
        """Verify Aadhaar using QR adapter."""
        if not self.aadhaar_verifier:
            logger.warning("Aadhaar verifier not configured - skipping verification")
            return DocumentDecision(
                status=DocumentDecisionStatus.ACCEPTED,
                reason="Aadhaar verification skipped - verifier not configured",
                fraud_signal_weight=0.3,
                metadata={"stage": "authenticity", "type": "aadhaar", "skipped": True}
            )
        
        result = await self.aadhaar_verifier.verify(file_bytes)
        
        # Map to DocumentDecision
        if not result.has_qr:
            return DocumentDecision(
                status=DocumentDecisionStatus.FLAGGED_HIGH_RISK,
                reason=result.reason,
                fraud_signal_weight=result.fraud_signal_weight,
                metadata={
                    "stage": "authenticity",
                    "type": "aadhaar",
                    "has_qr": False,
                    "extracted": result.extracted_data
                }
            )
        
        if not result.signature_valid:
            return DocumentDecision(
                status=DocumentDecisionStatus.FLAGGED_CRITICAL,
                reason=result.reason,
                fraud_signal_weight=result.fraud_signal_weight,
                metadata={
                    "stage": "authenticity",
                    "type": "aadhaar",
                    "has_qr": True,
                    "signature_valid": False,
                    "extracted": result.extracted_data
                }
            )
        
        return DocumentDecision(
            status=DocumentDecisionStatus.ACCEPTED,
            reason=result.reason,
            fraud_signal_weight=result.fraud_signal_weight,
            metadata={
                "stage": "authenticity",
                "type": "aadhaar",
                "verification": "passed",
                "extracted": result.extracted_data
            }
        )
    
    async def _verify_pan(self, extracted_text: str | None, holder_name: str | None) -> DocumentDecision:
        """Verify PAN using rule adapter."""
        if not self.pan_verifier:
            logger.warning("PAN verifier not configured - skipping verification")
            return DocumentDecision(
                status=DocumentDecisionStatus.ACCEPTED,
                reason="PAN verification skipped - verifier not configured",
                fraud_signal_weight=0.3,
                metadata={"stage": "authenticity", "type": "pan", "skipped": True}
            )
        
        # Extract PAN from text
        if not extracted_text:
            return DocumentDecision(
                status=DocumentDecisionStatus.FLAGGED_HIGH_RISK,
                reason="Cannot verify PAN - no text extracted",
                fraud_signal_weight=0.5,
                metadata={"stage": "authenticity", "type": "pan", "error": "no_text"}
            )
        
        pan_number = self.pan_verifier.extract_pan_from_text(extracted_text)
        if not pan_number:
            return DocumentDecision(
                status=DocumentDecisionStatus.FLAGGED_HIGH_RISK,
                reason="PAN number not found in document",
                fraud_signal_weight=0.6,
                metadata={"stage": "authenticity", "type": "pan", "error": "pan_not_found"}
            )
        
        result = await self.pan_verifier.verify(pan_number, holder_name)
        
        # Map to DocumentDecision
        if not result.format_valid:
            return DocumentDecision(
                status=DocumentDecisionStatus.FLAGGED_CRITICAL,
                reason=result.reason,
                fraud_signal_weight=result.fraud_signal_weight,
                metadata={
                    "stage": "authenticity",
                    "type": "pan",
                    "format_valid": False,
                    "extracted": result.extracted_data
                }
            )
        
        if not result.entity_type_match:
            return DocumentDecision(
                status=DocumentDecisionStatus.FLAGGED_HIGH_RISK,
                reason=result.reason,
                fraud_signal_weight=result.fraud_signal_weight,
                metadata={
                    "stage": "authenticity",
                    "type": "pan",
                    "entity_type_match": False,
                    "extracted": result.extracted_data
                }
            )
        
        if not result.is_valid:
            return DocumentDecision(
                status=DocumentDecisionStatus.FLAGGED_HIGH_RISK,
                reason=result.reason,
                fraud_signal_weight=result.fraud_signal_weight,
                metadata={
                    "stage": "authenticity",
                    "type": "pan",
                    "validation_failed": True,
                    "extracted": result.extracted_data
                }
            )
        
        return DocumentDecision(
            status=DocumentDecisionStatus.ACCEPTED,
            reason=result.reason,
            fraud_signal_weight=result.fraud_signal_weight,
            metadata={
                "stage": "authenticity",
                "type": "pan",
                "verification": "passed",
                "extracted": result.extracted_data
            }
        )
    
    # ── Helper Methods ────────────────────────────────────────────────────────
    
    def _detect_mime_from_bytes(self, file_bytes: bytes) -> str | None:
        """Detect MIME type from magic bytes."""
        if file_bytes[:4] == b'%PDF':
            return "application/pdf"
        elif file_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        elif file_bytes[:2] == b'\xff\xd8':
            return "image/jpeg"
        elif file_bytes[:2] in (b'II', b'MM'):
            return "image/tiff"
        elif file_bytes[:2] == b'BM':
            return "image/bmp"
        return None
    
    def _is_valid_file_structure(self, file_bytes: bytes) -> bool:
        """Basic validation of file structure (magic bytes check)."""
        if len(file_bytes) < 10:
            return False
        
        # Check magic bytes for supported formats
        return self._detect_mime_from_bytes(file_bytes) is not None
    
    def _types_match(self, detected: str, expected: str) -> bool:
        """Fuzzy match document types including all system DocumentType enum values."""
        detected = detected.lower().strip()
        expected = expected.lower().strip()

        # Exact match
        if detected == expected:
            return True

        # Generic catch-all ─ always accept (no meaningful type to match against)
        if expected in ("other", "OTHER"):
            return True

        # Canonical → list of natural-language aliases Gemini might return
        type_aliases: dict[str, list[str]] = {
            # ── Identity documents ──────────────────────────────────────────
            "aadhaar": ["aadhaar", "aadhaar card", "aadhar", "aadhar card", "uid", "uidai",
                        "aadhaar identity", "aadhaar id"],
            "pan": ["pan", "pan card", "permanent account number", "pan number"],
            # ── Medical ─────────────────────────────────────────────────────
            "discharge_summary": [
                "discharge summary", "discharge_summary", "discharge report",
                "hospital discharge", "discharge letter", "discharge certificate",
                "patient discharge",
            ],
            "medical_report": [
                "medical report", "medical_report", "lab report", "laboratory report",
                "diagnostic report", "test report", "blood report", "radiology report",
                "pathology report", "investigation report",
            ],
            "prescription": [
                "prescription", "medical prescription", "doctor prescription",
                "rx", "medicine prescription", "drug prescription",
            ],
            "invoice": [
                "invoice", "bill", "medical bill", "hospital bill", "medical invoice",
                "hospital invoice", "receipt", "billing statement", "payment receipt",
                "tax invoice", "insurance invoice", "policy document", "policy",
                "insurance policy",
            ],
            # ── Motor ────────────────────────────────────────────────────────
            "vehicle_rc": [
                "vehicle rc", "vehicle_rc", "registration certificate",
                "vehicle registration", "rc book", "vehicle registration certificate",
                "rc", "car rc", "bike rc", "registration card",
            ],
            "police_report": [
                "police report", "police_report", "fir", "first information report",
                "accident report", "police complaint", "police fir",
            ],
            "estimate": [
                "estimate", "repair estimate", "workshop estimate", "cost estimate",
                "damage estimate", "repair bill", "garage estimate", "quotation",
            ],
        }

        # Build reverse lookup: alias → canonical
        for canonical, aliases in type_aliases.items():
            all_forms = {canonical} | set(aliases)
            # Normalise expected
            if expected in all_forms or expected.replace("_", " ") in all_forms:
                # expected maps to this canonical; check detected
                if detected in all_forms or detected.replace("_", " ") in all_forms:
                    return True

        # Substring fallback: if expected key words appear in detected string
        exp_words = set(expected.replace("_", " ").split())
        det_words = set(detected.replace("_", " ").split())
        if exp_words and exp_words.issubset(det_words):
            return True

        return False
    
    async def _classify_with_gemini(
        self,
        file_bytes: bytes,
        expected_type: str
    ) -> dict[str, Any]:
        """
        Classify document using Gemini multimodal API.
        
        Forces strict JSON response with:
        - detected_type
        - is_relevant
        - confidence
        - reason
        """
        if not self.gemini_api_key:
            logger.warning("Gemini API key not configured - skipping LLM classification")
            return {
                "detected_type": expected_type,
                "is_relevant": True,
                "confidence": 0.5,
                "reason": "LLM classification skipped"
            }
        
        try:
            # Lazy-load Gemini
            if not self._gemini_model:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                self._gemini_model = genai.GenerativeModel("models/gemini-2.5-flash")
            
            # Prepare content part
            is_pdf = file_bytes[:4] == b'%PDF'
            
            if is_pdf:
                blob_data = base64.standard_b64encode(file_bytes).decode("utf-8")
                content_part = {
                    "inline_data": {"mime_type": "application/pdf", "data": blob_data}
                }
            else:
                # For images, encode directly
                mime_type = self._detect_mime_from_bytes(file_bytes) or "image/jpeg"
                blob_data = base64.standard_b64encode(file_bytes).decode("utf-8")
                content_part = {
                    "inline_data": {"mime_type": mime_type, "data": blob_data}
                }
            
            # Classification prompt using the exact type tokens this system uses
            prompt = f"""You are a document classifier for an insurance claims system.

Analyze this document and determine its type. Use ONLY one of the following type tokens:
- discharge_summary  (hospital discharge summary / discharge letter)
- medical_report     (lab report, diagnostic report, radiology, pathology)
- prescription       (doctor prescription / Rx)
- invoice            (hospital bill, medical invoice, policy document, payment receipt)
- vehicle_rc         (vehicle registration certificate / RC book)
- police_report      (FIR / first information report / accident report)
- estimate           (repair estimate / workshop quotation)
- aadhaar            (Aadhaar card / UIDAI identity card)
- pan                (PAN card / Permanent Account Number card)
- other              (anything else)

Expected type for this upload: "{expected_type}"

Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "detected_type": "<one of the tokens above>",
  "is_relevant": true/false,
  "confidence": 0.0-1.0,
  "reason": "one sentence"
}}"""
            
            # Call Gemini in threadpool
            loop = asyncio.get_running_loop()
            
            def _call():
                response = self._gemini_model.generate_content([content_part, prompt])
                return response.text
            
            raw_text = await loop.run_in_executor(None, _call)
            
            # Parse JSON response
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
                cleaned = cleaned.rsplit("```", 1)[0].strip()
            
            result = json.loads(cleaned)
            
            return {
                "detected_type": result.get("detected_type", "unknown"),
                "is_relevant": result.get("is_relevant", False),
                "confidence": float(result.get("confidence", 0.0)),
                "reason": result.get("reason", "")
            }
        
        except Exception as exc:
            logger.error(f"Gemini classification failed: {exc}", exc_info=True)
            # Fail-open with low confidence
            return {
                "detected_type": expected_type,
                "is_relevant": True,
                "confidence": 0.3,
                "reason": f"Classification error: {str(exc)}"
            }


# ── Context Provider for Narrative Layer ──────────────────────────────────────
async def get_document_validation_context(
    validation_status: str,
    validation_reason: str,
    validation_metadata: dict[str, Any]
) -> dict[str, Any]:
    """
    Build context dictionary for Layer 6 narrative generation.
    
    This provides the AI agent with structured validation data
    to incorporate into fraud explanations.
    
    Args:
        validation_status: Document validation status
        validation_reason: Validation reason/explanation
        validation_metadata: Detailed validation metadata
    
    Returns:
        Context dictionary for narrative prompt
    """
    return {
        "validation_status": validation_status,
        "validation_reason": validation_reason,
        "validation_stage": validation_metadata.get("stage", "unknown"),
        "document_type": validation_metadata.get("type", "unknown"),
        "authenticity_verified": validation_metadata.get("verification") == "passed",
        "has_qr": validation_metadata.get("has_qr"),
        "signature_valid": validation_metadata.get("signature_valid"),
        "format_valid": validation_metadata.get("format_valid"),
        "confidence": validation_metadata.get("confidence"),
        "extracted_data": validation_metadata.get("extracted", {}),
    }
