"""
Document service — upload, encrypt, extract (LangExtract), and retrieve.
Structured extraction is done exclusively via langextract + Gemini.
No OCR, no heuristics — Gemini reads the document.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.constants import AuditAction
from app.core.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.models.claim import Claim
from app.models.document import Document
from app.models.document_access_log import DocumentAccessLog
from app.services.audit_service import log_action
from app.services.document_gatekeeper import DocumentGatekeeper, DocumentDecisionStatus
from app.services.gov_adapters.aadhaar_verification import AadhaarQRVerifier
from app.services.gov_adapters.pan_verification import PANRuleVerifier

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None
_gatekeeper: DocumentGatekeeper | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return _fernet


def _get_gatekeeper() -> DocumentGatekeeper:
    """Get or create singleton DocumentGatekeeper instance."""
    global _gatekeeper
    if _gatekeeper is None:
        _gatekeeper = DocumentGatekeeper(
            aadhaar_verifier=AadhaarQRVerifier(),
            pan_verifier=PANRuleVerifier(),
            gemini_api_key=settings.GCP_API_KEY
        )
    return _gatekeeper


# ── Upload ────────────────────────────────────────────────────────────────────
async def upload_document(
    claim_id: str,
    uploader_id: str,
    role: str,
    file: UploadFile,
    document_type: str,
    db: AsyncSession,
) -> Document:
    # Verify claim exists and user has access
    result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
    claim = result.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim not found")
    if role == "CUSTOMER" and str(claim.user_id) != uploader_id:
        raise PermissionDeniedError("Not your claim")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise BusinessRuleError(f"File too large (max {settings.MAX_UPLOAD_SIZE // 1024 // 1024} MB)")

    # Extract structured data FIRST (needed for validation)
    extraction = await _extract(content, file.content_type or "", document_type)
    extracted_text = extraction.get("raw_text", "") or str(extraction.get("fields", {}))
    
    # Validate document using DocumentGatekeeper
    gatekeeper = _get_gatekeeper()
    validation_decision = await gatekeeper.validate_document(
        file_bytes=content,
        filename=file.filename or "unknown",
        expected_type=document_type,
        extracted_text=extracted_text,
        holder_name=None  # Could extract from claim/user data if available
    )
    
    # Hard reject if validation failed
    if validation_decision.status == DocumentDecisionStatus.REJECTED_INVALID:
        raise BusinessRuleError(validation_decision.reason)
    
    # Encrypt and persist
    encrypted = _get_fernet().encrypt(content)
    storage_dir = Path(settings.ENCRYPTED_STORAGE_DIR) / claim_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / f"{uuid.uuid4()}.enc"
    file_path.write_bytes(encrypted)

    doc = Document(
        id=uuid.uuid4(),
        claim_id=uuid.UUID(claim_id),
        uploader_id=uuid.UUID(uploader_id),
        document_type=document_type,
        storage_path=str(file_path),
        original_filename=file.filename,
        content_type=file.content_type,
        extracted_data=extraction.get("fields"),
        extraction_confidence=extraction.get("confidence"),
        requires_manual_review=extraction.get("confidence", 1.0) < 0.5,
        # Validation results from DocumentGatekeeper
        validation_status=validation_decision.status.value,
        validation_reason=validation_decision.reason,
        authenticity_metadata_json=validation_decision.metadata,
        fraud_signal_weight=validation_decision.fraud_signal_weight,
    )
    db.add(doc)
    await log_action(
        db=db,
        action_type=AuditAction.DOCUMENT_UPLOADED,
        entity_type="DOCUMENT",
        actor_id=uploader_id,
        entity_id=str(doc.id),
        metadata={"claim_id": claim_id, "type": document_type},
    )
    await db.commit()
    await db.refresh(doc)
    return doc


# ── List documents for a claim ───────────────────────────────────────────────
async def list_documents(
    claim_id: str, requester_id: str, role: str, db: AsyncSession
) -> list[Document]:
    """Return all Document rows for a given claim, enforcing ownership for CUSTOMER."""
    claim_result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
    claim = claim_result.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim not found")
    if role == "CUSTOMER" and str(claim.user_id) != requester_id:
        raise PermissionDeniedError("Not your claim")
    result = await db.execute(
        select(Document).where(Document.claim_id == uuid.UUID(claim_id)).order_by(Document.created_at)
    )
    return list(result.scalars().all())


# ── Retrieval (decrypt + access log) ─────────────────────────────────────────
async def get_document_bytes(
    document_id: str, requester_id: str, role: str, db: AsyncSession
) -> tuple[bytes, Document]:
    result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document not found")

    if role == "CUSTOMER":
        claim_result = await db.execute(select(Claim).where(Claim.id == doc.claim_id))
        claim = claim_result.scalar_one_or_none()
        if not claim or str(claim.user_id) != requester_id:
            raise PermissionDeniedError("Not your document")

    encrypted = Path(doc.storage_path).read_bytes()
    raw = _get_fernet().decrypt(encrypted)

    # Write access log
    access_log = DocumentAccessLog(
        id=uuid.uuid4(),
        user_id=uuid.UUID(requester_id),
        document_id=doc.id,
        action="DOWNLOADED",
    )
    db.add(access_log)
    await db.commit()
    return raw, doc


# ── Gemini-powered document extraction (handles text AND scanned/image PDFs) ──
async def _extract(content: bytes, content_type: str, doc_type: str) -> dict[str, Any]:
    """
    Extract structured fields from an insurance document using Gemini multimodal API.

    Strategy:
    1. PDFs  → sent as inline binary blob to Gemini (works for both text-layer
               and scanned/image-only PDFs — Gemini reads them natively)
    2. Other → try pypdf text extraction first; if empty, decode as UTF-8 and
               pass as plain text
    Gemini returns a structured JSON object which we store.
    """
    import asyncio
    import base64
    import io
    import json
    from functools import partial

    try:
        import google.generativeai as genai
        from app.config import settings

        genai.configure(api_key=settings.GCP_API_KEY)

        # ── Step 1: Determine MIME type and prepare content part ──────────────
        is_pdf = content[:4] == b"%PDF" or "pdf" in (content_type or "").lower()

        doc_text = ""  # Keep track of extracted text for validation
        if is_pdf:
            mime = "application/pdf"
            blob_data = base64.standard_b64encode(content).decode("utf-8")
            content_part = {"inline_data": {"mime_type": mime, "data": blob_data}}
            method = "gemini-native-pdf"
        else:
            # Non-PDF: try to get text via pypdf fallback, else raw bytes
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(content))
                doc_text = "\n".join(p.extract_text() or "" for p in reader.pages).strip()
            except Exception:
                pass
            if not doc_text:
                doc_text = content.decode("utf-8", errors="replace").strip()
            if not doc_text:
                logger.warning("No content to extract from document (type=%s)", content_type)
                return {"fields": {}, "confidence": 0.0, "method": "none", "raw_text": ""}
            content_part = doc_text
            method = "gemini-text"

        # ── Step 2: Build Gemini prompt ────────────────────────────────────────
        prompt = f"""You are an insurance document parser. Carefully read the attached {doc_type} document and extract ALL key structured fields.

Extract the following fields (use null if not found):
- patient_name / claimant_name
- date_of_service / date_of_incident
- provider_name / hospital_name
- diagnosis / incident_description
- total_amount (numeric value only)
- policy_number
- claim_number / reference_number
- document_id / id_number
- address
- phone_number
- any other significant identifiers

Respond ONLY with a valid JSON object like:
{{
  "patient_name": {{\"text\": \"...\"}},
  "date_of_service": {{\"text\": \"...\"}},
  "total_amount": {{\"text\": \"...\", \"value\": 0.0}},
  ...
}}
Do not include any explanation or markdown — only the raw JSON object."""

        # ── Step 3: Call Gemini in a threadpool ────────────────────────────────
        model = genai.GenerativeModel("models/gemini-2.5-flash")

        def _call_gemini():
            response = model.generate_content([content_part, prompt])
            return response.text

        loop = asyncio.get_running_loop()
        raw_text = await loop.run_in_executor(None, _call_gemini)

        # ── Step 4: Parse JSON response ────────────────────────────────────────
        # Strip markdown fences if Gemini wrapped the response
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0].strip()

        try:
            fields: dict[str, Any] = json.loads(cleaned)
        except json.JSONDecodeError:
            # Partial salvage: try to find a JSON object inside the text
            import re
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            fields = json.loads(match.group()) if match else {}

        # Drop null/empty fields
        fields = {k: v for k, v in fields.items() if v and v != {"text": None}}

        confidence = 0.90 if fields else 0.0
        logger.info("Extraction complete: %d fields via %s", len(fields), method)
        return {"fields": fields, "confidence": confidence, "method": method, "raw_text": raw_text[:1000]}  # First 1000 chars

    except ImportError:
        logger.error("google-generativeai not installed — run: pip install google-generativeai")
    except Exception as exc:
        logger.warning("Gemini extraction failed: %s", exc, exc_info=True)

    # Fail-open: upload proceeds, document flagged for manual review
    return {"fields": {}, "confidence": 0.0, "method": "none", "raw_text": ""}


# ── Update extracted data (manual correction) ──────────────────────────────────
async def update_extracted_data(
    document_id: str,
    extracted_data: dict[str, Any],
    requires_manual_review: bool | None,
    requester_id: str,
    role: str,
    db: AsyncSession,
) -> Document:
    """Update extracted data for a document (user correction)."""
    result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document not found")

    if role == "CUSTOMER":
        claim_result = await db.execute(select(Claim).where(Claim.id == doc.claim_id))
        claim = claim_result.scalar_one_or_none()
        if not claim or str(claim.user_id) != requester_id:
            raise PermissionDeniedError("Not your document")

    # Update the extracted data
    doc.extracted_data = extracted_data
    if requires_manual_review is not None:
        doc.requires_manual_review = requires_manual_review

    await db.commit()
    await db.refresh(doc)
    return doc
