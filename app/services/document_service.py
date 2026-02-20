"""
Document service — upload, encrypt, extract (LangExtract), and retrieve.
Structured extraction is done exclusively via langextract + Gemini.
No OCR, no heuristics — Gemini reads the document.
"""
from __future__ import annotations

import hashlib
import logging
import os
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

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return _fernet


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

    # Encrypt and persist
    encrypted = _get_fernet().encrypt(content)
    storage_dir = Path(settings.ENCRYPTED_STORAGE_DIR) / claim_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / f"{uuid.uuid4()}.enc"
    file_path.write_bytes(encrypted)

    # Extract structured data
    extraction = await _extract(content, file.content_type or "", document_type)

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


# ── LangExtract — Gemini-powered document parsing (no OCR, no heuristics) ─────
async def _extract(content: bytes, content_type: str, doc_type: str) -> dict[str, Any]:
    """
    Extract structured fields from an insurance document using LangExtract + Gemini.
    Gemini does all the reading — no OCR, no keyword parsing, no heuristics.
    """
    import asyncio
    import tempfile
    from functools import partial

    try:
        import langextract as lx
        from app.config import settings

        # Persist bytes to a temp file — langextract accepts file paths
        suffix = ".pdf" if "pdf" in (content_type or "") else ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(content)
            tmp_path = f.name

        try:
            prompt = (
                f"Extract all key structured fields from this {doc_type} insurance document. "
                "Look for: patient or claimant name, date of service or incident, "
                "provider or hospital name, diagnosis or incident description, "
                "total claim amount (as a number), receipt or reference number, "
                "and any other significant identifiers. "
                "Use exact text from the document for extraction_text."
            )

            # One-shot example to guide Gemini's extraction format
            examples = [
                lx.data.ExampleData(
                    text=(
                        "Patient: Rahul Sharma | Date: 12-Jan-2025 | "
                        "Hospital: Apollo Delhi | Diagnosis: Appendicitis | "
                        "Total: ₹42,500 | Receipt: RX-20250112-001"
                    ),
                    extractions=[
                        lx.data.Extraction(extraction_class="patient_name",    extraction_text="Rahul Sharma",        attributes={}),
                        lx.data.Extraction(extraction_class="date_of_service",  extraction_text="12-Jan-2025",         attributes={}),
                        lx.data.Extraction(extraction_class="provider_name",   extraction_text="Apollo Delhi",        attributes={}),
                        lx.data.Extraction(extraction_class="diagnosis",       extraction_text="Appendicitis",        attributes={}),
                        lx.data.Extraction(extraction_class="total_amount",    extraction_text="₹42,500",             attributes={"value": 42500.0}),
                        lx.data.Extraction(extraction_class="receipt_number",  extraction_text="RX-20250112-001",     attributes={}),
                    ],
                )
            ]

            # lx.extract is synchronous — run in threadpool so we don't block the event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                partial(
                    lx.extract,
                    text_or_documents=tmp_path,
                    prompt_description=prompt,
                    examples=examples,
                    model_id="gemini-2.5-flash",
                    api_key=settings.GCP_API_KEY,
                ),
            )

            # Build a clean dict: extraction_class → extraction_text (+ attributes)
            fields: dict[str, Any] = {}
            for ext in result.extractions:
                key = ext.extraction_class
                fields[key] = {
                    "text": ext.extraction_text,
                    **({"attributes": ext.attributes} if ext.attributes else {}),
                }

            return {"fields": fields, "confidence": 0.90, "method": "langextract+gemini"}

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except ImportError:
        logger.error("langextract is not installed — run: pip install langextract")
    except Exception as exc:
        logger.warning("LangExtract extraction failed: %s", exc)

    # Fail-open: upload proceeds, document flagged for manual review
    return {"fields": {}, "confidence": 0.0, "method": "none"}

