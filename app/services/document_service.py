"""
Document service — upload, encrypt, extract (LangExtract), and retrieve.
Structured extraction is done exclusively via langextract + Gemini.
No OCR, no heuristics — Gemini reads the document.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from fastapi import BackgroundTasks, UploadFile
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
    background_tasks: BackgroundTasks | None = None,
) -> Document:
    """
    Save the file immediately and return the Document record.
    Gemini extraction + DocumentGatekeeper validation run asynchronously
    in the background so the HTTP response is never delayed by a slow
    third-party AI API call.
    """
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

    # Encrypt and persist immediately — do NOT wait for Gemini here
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
        extracted_data=None,
        extraction_confidence=None,
        requires_manual_review=True,   # conservative default until extraction runs
        # Extraction/validation are pending — updated by background task
        validation_status="pending",
        validation_reason="AI extraction queued — check back shortly",
        authenticity_metadata_json=None,
        fraud_signal_weight=None,
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

    # Schedule background extraction + validation (non-blocking)
    _original_filename = file.filename or "unknown"
    _doc_id = str(doc.id)
    if background_tasks is not None:
        background_tasks.add_task(
            _run_extraction_background,
            doc_id=_doc_id,
            content=content,
            content_type=file.content_type or "",
            doc_type=document_type,
            original_filename=_original_filename,
        )
    else:
        # Fallback when called outside a request context (e.g. tests)
        asyncio.ensure_future(
            _run_extraction_background(
                doc_id=_doc_id,
                content=content,
                content_type=file.content_type or "",
                doc_type=document_type,
                original_filename=_original_filename,
            )
        )

    return doc


async def _run_extraction_background(
    doc_id: str,
    content: bytes,
    content_type: str,
    doc_type: str,
    original_filename: str = "unknown",
) -> None:
    """
    Run Gemini extraction + DocumentGatekeeper validation in the background.
    Opens its own DB session so this runs safely after the HTTP response
    has already been sent.
    """
    from app.db.session import AsyncSessionLocal

    logger.info("Background extraction started for document %s", doc_id)
    try:
        # ── 1. Gemini extraction (may take 20-40 s) ────────────────────────
        extraction = await _extract(content, content_type, doc_type)
        extracted_text = extraction.get("raw_text", "") or str(extraction.get("fields", {}))

        # ── 2. DocumentGatekeeper validation ──────────────────────────────
        gatekeeper = _get_gatekeeper()
        validation_decision = await gatekeeper.validate_document(
            file_bytes=content,
            filename=original_filename,
            expected_type=doc_type,
            extracted_text=extracted_text,
            holder_name=None,
        )

        # ── 3. Persist results ─────────────────────────────────────────────
        async with AsyncSessionLocal() as bg_db:
            result = await bg_db.execute(select(Document).where(Document.id == uuid.UUID(doc_id)))
            doc = result.scalar_one_or_none()
            if doc is None:
                logger.warning("Background extraction: document %s not found in DB", doc_id)
                return

            doc.extracted_data = extraction.get("fields")
            doc.extraction_confidence = extraction.get("confidence")
            doc.requires_manual_review = extraction.get("confidence", 1.0) < 0.5
            doc.validation_status = validation_decision.status.value
            doc.validation_reason = validation_decision.reason
            doc.authenticity_metadata_json = validation_decision.metadata
            doc.fraud_signal_weight = validation_decision.fraud_signal_weight

            await bg_db.commit()
            logger.info(
                "Background extraction complete for document %s — status=%s fields=%d",
                doc_id,
                validation_decision.status.value,
                len(extraction.get("fields") or {}),
            )

    except Exception as exc:
        logger.error(
            "Background extraction failed for document %s: %s",
            doc_id, exc, exc_info=True,
        )
        # Mark the document so staff know to review it manually
        try:
            from app.db.session import AsyncSessionLocal as _ASL
            async with _ASL() as bg_db:
                result = await bg_db.execute(select(Document).where(Document.id == uuid.UUID(doc_id)))
                doc = result.scalar_one_or_none()
                if doc:
                    doc.validation_status = "extraction_failed"
                    doc.validation_reason = f"Automated extraction error: {exc}"
                    doc.requires_manual_review = True
                    await bg_db.commit()
        except Exception:
            pass  # best-effort


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
    import io
    import json
    from functools import partial

    try:
        from google import genai
        from google.genai import types as _genai_types
        from app.config import settings

        _client = genai.Client(api_key=settings.GCP_API_KEY)

        # ── Step 1: Determine MIME type and prepare content part ──────────────
        is_pdf = content[:4] == b"%PDF" or "pdf" in (content_type or "").lower()

        doc_text = ""  # Keep track of extracted text for validation
        if is_pdf:
            mime = "application/pdf"
            content_part = _genai_types.Part.from_bytes(data=content, mime_type=mime)
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
        # Tailor the field list to the document type so Gemini focuses on what matters
        _type_hints = {
            "DISCHARGE_SUMMARY": (
                "patient_name, date_of_admission, date_of_discharge, "
                "hospital_name, ward_department, treating_doctor, diagnosis, "
                "procedures_performed, total_bill_amount, discharge_condition"
            ),
            "INVOICE": (
                "hospital_name, patient_name, invoice_number, invoice_date, "
                "total_amount, itemised_charges, gst_amount, payable_amount"
            ),
            "MEDICAL_REPORT": (
                "patient_name, report_date, lab_name, test_name, "
                "results_summary, reference_range, ordering_doctor"
            ),
            "PRESCRIPTION": (
                "patient_name, doctor_name, clinic_name, prescription_date, "
                "medications_list, dosage_instructions, diagnosis"
            ),
            "POLICE_REPORT": (
                "complainant_name, fir_number, date_of_incident, "
                "place_of_incident, description_of_incident, officer_name, police_station"
            ),
        }
        field_guidance = _type_hints.get(
            doc_type.upper(),
            (
                "patient_name / claimant_name, date_of_service / date_of_incident, "
                "provider_name / hospital_name, diagnosis / incident_description, "
                "total_amount, policy_number, claim_number, document_id, address, phone_number"
            ),
        )
        prompt = f"""You are an insurance document parser. Carefully read the attached {doc_type} document and extract ALL key structured fields.

This is a {doc_type} document. Extract the following fields (use null if not found):
{field_guidance}

Also extract any other significant identifiers or amounts present in the document.

Respond ONLY with a valid JSON object like:
{{
  "patient_name": {{\"text\": \"...\"}},
  "date_of_admission": {{\"text\": \"...\"}},
  "total_amount": {{\"text\": \"...\", \"value\": 0.0}},
  ...
}}
Do not include any explanation or markdown — only the raw JSON object."""

        # ── Step 3: Call Gemini in a threadpool ────────────────────────────────
        def _call_gemini():
            response = _client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[content_part, prompt],
            )
            return response.text

        loop = asyncio.get_running_loop()
        raw_text = await loop.run_in_executor(None, _call_gemini)
        logger.info("Gemini raw response for %s (first 500 chars): %s", doc_type, raw_text[:500])

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
        logger.info("Extraction complete: %d fields (%s) via %s", len(fields), list(fields.keys()), method)
        return {"fields": fields, "confidence": confidence, "method": method, "raw_text": raw_text[:2000]}

    except ImportError:
        logger.error("google-genai not installed — run: pip install google-genai")
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
