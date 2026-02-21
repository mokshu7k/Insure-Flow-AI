"""
ClaimDocument service — template-aware OCR pipeline.

Pipeline:
  upload → create ClaimDocument (PENDING) → background task:
    1. Fetch DocumentRequirement for claim's policy_type_id + document_type_code
    2. Build extraction prompt via extraction_service.build_extraction_prompt()
    3. Call Gemini multimodal API (same pattern as document_service._extract)
    4. Detect wrong-document (Gemini flag or gatekeeper)
    5. Validate required fields, run template validation_rules
    6. Call extraction_service.promote_fields() → write promoted columns
    7. Run DocumentGatekeeper for authenticity
    8. Run cross-document consistency checks against other ClaimDocuments on same claim
    9. Persist all results to ClaimDocument row

This service is the ONLY place that creates ClaimDocument rows.
The legacy document_service.py still handles the old Document model.
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.models.claim import Claim
from app.models.claim_document import ClaimDocument
from app.models.document_requirement import DocumentRequirement
from app.models.policy import Policy
from app.services.extraction_service import (
    CONSISTENCY_RULES,
    build_extraction_prompt,
    promote_fields,
)

logger = logging.getLogger(__name__)

_fernet_instance: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        _fernet_instance = Fernet(settings.ENCRYPTION_KEY.encode())
    return _fernet_instance


# ── Upload ────────────────────────────────────────────────────────────────────

async def upload_claim_document(
    claim_id: str,
    uploader_id: str,
    role: str,
    file: UploadFile,
    document_type_code: str,
    document_requirement_id: str | None,
    db: AsyncSession,
    background_tasks: BackgroundTasks | None = None,
) -> ClaimDocument:
    """
    Encrypt and persist the file immediately, return the ClaimDocument with
    ocr_status=PENDING. Template-aware Gemini extraction runs asynchronously.
    """
    # Verify claim exists and caller has access
    result = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
    claim = result.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim not found")
    if role == "CUSTOMER" and str(claim.user_id) != uploader_id:
        raise PermissionDeniedError("Not your claim")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise BusinessRuleError(
            f"File too large (max {settings.MAX_UPLOAD_SIZE // 1024 // 1024} MB)"
        )

    # Encrypt + store
    encrypted = _get_fernet().encrypt(content)
    storage_dir = Path(settings.ENCRYPTED_STORAGE_DIR) / claim_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / f"{uuid.uuid4()}.enc"
    file_path.write_bytes(encrypted)

    req_uuid = uuid.UUID(document_requirement_id) if document_requirement_id else None

    doc = ClaimDocument(
        id=uuid.uuid4(),
        claim_id=uuid.UUID(claim_id),
        uploader_id=uuid.UUID(uploader_id),
        document_type_code=document_type_code,
        document_requirement_id=req_uuid,
        storage_path=str(file_path),
        original_filename=file.filename,
        content_type=file.content_type,
        ocr_status="PENDING",
        validation_status="PENDING",
        requires_manual_review=True,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Schedule background template-aware extraction
    _doc_id = str(doc.id)
    _cid = claim_id
    _content = content
    _ctype = file.content_type or ""
    _fname = file.filename or "unknown"

    if background_tasks is not None:
        background_tasks.add_task(
            _run_extraction_background,
            doc_id=_doc_id,
            claim_id=_cid,
            content=_content,
            content_type=_ctype,
            document_type_code=document_type_code,
            original_filename=_fname,
        )
    else:
        asyncio.ensure_future(
            _run_extraction_background(
                doc_id=_doc_id,
                claim_id=_cid,
                content=_content,
                content_type=_ctype,
                document_type_code=document_type_code,
                original_filename=_fname,
            )
        )

    return doc


# ── Background extraction ─────────────────────────────────────────────────────

async def _run_extraction_background(
    doc_id: str,
    claim_id: str,
    content: bytes,
    content_type: str,
    document_type_code: str,
    original_filename: str = "unknown",
) -> None:
    """Template-aware Gemini extraction + gatekeeper + consistency checks."""
    from app.db.session import AsyncSessionLocal
    from app.services.document_gatekeeper import DocumentGatekeeper
    from app.services.gov_adapters.aadhaar_verification import AadhaarQRVerifier
    from app.services.gov_adapters.pan_verification import PANRuleVerifier

    logger.info("ClaimDocument background extraction started for %s", doc_id)

    try:
        async with AsyncSessionLocal() as bg_db:
            # ── Fetch claim → policy → policy_type for template lookup ──
            claim_res = await bg_db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
            claim = claim_res.scalar_one_or_none()

            policy_type_id: uuid.UUID | None = None
            if claim and claim.policy_id:
                pol_res = await bg_db.execute(select(Policy).where(Policy.id == claim.policy_id))
                policy = pol_res.scalar_one_or_none()
                if policy:
                    policy_type_id = policy.policy_type_id

            # ── Fetch DocumentRequirement template ──
            requirement: DocumentRequirement | None = None
            if policy_type_id:
                req_res = await bg_db.execute(
                    select(DocumentRequirement).where(
                        DocumentRequirement.policy_type_id == policy_type_id,
                        DocumentRequirement.document_type_code == document_type_code,
                    )
                )
                requirement = req_res.scalar_one_or_none()

            # ── Build extraction prompt ──
            if requirement and requirement.extraction_template:
                prompt = build_extraction_prompt(
                    extraction_template=requirement.extraction_template,
                    document_type_code=document_type_code,
                    display_name=requirement.display_name or document_type_code,
                )
                template_snapshot = requirement.extraction_template
            else:
                # Fallback: generic prompt (no template)
                prompt = _generic_fallback_prompt(document_type_code)
                template_snapshot = None

            # ── Call Gemini ─────────────────────────────────────────────────
            extraction = await _call_gemini(content, content_type, prompt)
            fields: dict[str, Any] = extraction.get("fields", {})
            confidence: float = extraction.get("confidence", 0.0)
            raw_text: str = extraction.get("raw_text", "")

            # ── Detect wrong document type ──────────────────────────────────
            wrong_type = fields.pop("_wrong_document_type", False)
            detected_type = fields.pop("_detected_type", None)
            extraction_notes = fields.pop("_extraction_notes", None)

            # ── Find missing required fields ────────────────────────────────
            missing_fields: list[str] = []
            if requirement and requirement.extraction_template:
                required_keys = [
                    f["key"]
                    for f in requirement.extraction_template.get("fields", [])
                    if f.get("required", False)
                ]
                missing_fields = [k for k in required_keys if not fields.get(k)]

            # ── Compute real confidence from template coverage ───────────────
            if not fields:
                confidence = 0.0
            elif requirement and requirement.extraction_template:
                template_fields = requirement.extraction_template.get("fields", [])
                req_keys = [f["key"] for f in template_fields if f.get("required", False)]
                opt_keys = [f["key"] for f in template_fields if not f.get("required", False)]
                if req_keys:
                    req_score = (len(req_keys) - len(missing_fields)) / len(req_keys)
                else:
                    req_score = 1.0
                opt_score = (
                    sum(1 for k in opt_keys if fields.get(k)) / len(opt_keys)
                    if opt_keys else 1.0
                )
                # Required fields are 85% of the score, optional 15%
                confidence = round(req_score * 0.85 + opt_score * 0.15, 4)
            else:
                # No template — rough heuristic: more fields = higher confidence, cap at 0.80
                confidence = round(min(0.80, 0.40 + len(fields) * 0.04), 4)

            # ── Run template validation rules ───────────────────────────────
            rule_failures: list[str] = []
            if requirement and requirement.validation_rules:
                rule_failures = _apply_validation_rules(
                    fields, requirement.validation_rules.get("rules", [])
                )

            # ── Promote fields to typed columns ─────────────────────────────
            promoted = promote_fields(document_type_code, fields)

            # ── Determine validation status ─────────────────────────────────
            if wrong_type:
                val_status = "REJECTED"
                val_reason = (
                    f"Wrong document type — uploaded appears to be {detected_type or 'unknown'}, "
                    f"expected {document_type_code}."
                )
            elif missing_fields:
                val_status = "NEEDS_RESUBMISSION"
                val_reason = f"Required fields missing: {', '.join(missing_fields)}"
            elif rule_failures:
                val_status = "NEEDS_RESUBMISSION"
                val_reason = "; ".join(rule_failures)
            else:
                val_status = "ACCEPTED"
                val_reason = (
                    f"Extracted {len(fields)} fields with {confidence*100:.0f}%% confidence."
                    + (f" Notes: {extraction_notes}" if extraction_notes else "")
                )

            # ── DocumentGatekeeper authenticity check ───────────────────────
            gatekeeper = DocumentGatekeeper(
                aadhaar_verifier=AadhaarQRVerifier(),
                pan_verifier=PANRuleVerifier(),
                gemini_api_key=settings.GCP_API_KEY,
            )
            gatekeeper_decision = await gatekeeper.validate_document(
                file_bytes=content,
                filename=original_filename,
                expected_type=document_type_code,
                extracted_text=raw_text or str(fields),
                holder_name=promoted.get("patient_name"),
            )

            # Escalate if gatekeeper flags it
            if gatekeeper_decision.status.value in {"flagged_high_risk", "flagged_critical", "rejected_invalid"}:
                if val_status == "ACCEPTED":
                    val_status = "FLAGGED"
                    val_reason = gatekeeper_decision.reason

            # ── Persist ──────────────────────────────────────────────────────
            doc_res = await bg_db.execute(
                select(ClaimDocument).where(ClaimDocument.id == uuid.UUID(doc_id))
            )
            doc = doc_res.scalar_one_or_none()
            if doc is None:
                logger.warning("ClaimDocument %s not found during persistence", doc_id)
                return

            doc.ocr_status = "COMPLETED"
            doc.extracted_data = fields
            doc.extraction_confidence = confidence
            doc.extraction_template_used = template_snapshot
            doc.missing_fields = missing_fields or None
            doc.validation_status = val_status
            doc.validation_reason = val_reason
            doc.authenticity_metadata = gatekeeper_decision.metadata
            doc.fraud_signal_weight = float(gatekeeper_decision.fraud_signal_weight)
            doc.requires_manual_review = (
                confidence < 0.5 or bool(missing_fields) or wrong_type
            )

            # Apply promoted columns
            for col, val in promoted.items():
                setattr(doc, col, val)

            await bg_db.commit()

            # ── Cross-document consistency check ─────────────────────────────
            await _check_consistency(bg_db, claim_id, doc_id, document_type_code, promoted)

            logger.info(
                "ClaimDocument %s extraction done — status=%s fields=%d missing=%d",
                doc_id, val_status, len(fields), len(missing_fields),
            )

    except Exception as exc:
        logger.error("ClaimDocument background extraction failed for %s: %s", doc_id, exc, exc_info=True)
        try:
            from app.db.session import AsyncSessionLocal as _ASL
            async with _ASL() as bg_db:
                res = await bg_db.execute(
                    select(ClaimDocument).where(ClaimDocument.id == uuid.UUID(doc_id))
                )
                doc = res.scalar_one_or_none()
                if doc:
                    doc.ocr_status = "FAILED"
                    doc.validation_status = "FLAGGED"
                    doc.validation_reason = f"Extraction error: {exc}"
                    doc.requires_manual_review = True
                    await bg_db.commit()
        except Exception:
            pass


# ── Gemini call ───────────────────────────────────────────────────────────────

async def _call_gemini(content: bytes, content_type: str, prompt: str) -> dict[str, Any]:
    """Call Gemini with the document bytes and the given prompt string."""
    import json
    from functools import partial

    try:
        from google import genai
        from google.genai import types as _genai_types

        _client = genai.Client(api_key=settings.GCP_API_KEY)

        is_pdf = content[:4] == b"%PDF" or "pdf" in (content_type or "").lower()
        if is_pdf:
            content_part = _genai_types.Part.from_bytes(
                data=content, mime_type="application/pdf"
            )
        elif content_type and content_type.startswith("image/"):
            content_part = _genai_types.Part.from_bytes(
                data=content, mime_type=content_type
            )
        else:
            # Try to decode as text; if that fails use UTF-8 replace
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = content.decode("utf-8", errors="replace")
            content_part = text

        def _call():
            response = _client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[content_part, prompt],
            )
            return response.text

        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, _call)
        logger.info("Gemini raw (first 400): %s", raw[:400])

        # Strip markdown fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0].strip()

        try:
            fields: dict[str, Any] = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            fields = json.loads(match.group()) if match else {}

        # Strip null/empty values
        fields = {k: v for k, v in fields.items() if v not in (None, "", {}, [])}
        # Return 1.0 as a raw signal ("Gemini returned something").
        # Real quality-based confidence is calculated at the call site
        # once we know which required template fields are present.
        confidence = 1.0 if fields else 0.0
        return {"fields": fields, "confidence": confidence, "raw_text": raw[:2000]}

    except ImportError:
        logger.error("google-genai not installed")
    except Exception as exc:
        logger.warning("Gemini call failed: %s", exc, exc_info=True)

    return {"fields": {}, "confidence": 0.0, "raw_text": ""}


# ── Generic fallback prompt ───────────────────────────────────────────────────

def _generic_fallback_prompt(doc_type_code: str) -> str:
    return f"""You are an insurance document parser.
Extract all key structured fields from this {doc_type_code} document.
Return ONLY a valid JSON object. No markdown fences.
Include patient_name, hospital_name, date, total_amount, and all other relevant fields.
If this document is NOT a {doc_type_code}, set "_wrong_document_type": true and "_detected_type": "<type>".
Add "_extraction_notes" with any observations."""


# ── Template validation rules ─────────────────────────────────────────────────

def _apply_validation_rules(
    fields: dict[str, Any],
    rules: list[dict[str, Any]],
) -> list[str]:
    """Apply template validation_rules.rules against extracted fields.
    Returns a list of human-readable failure messages.
    """
    failures: list[str] = []
    for rule in rules:
        field = rule.get("field")
        check = rule.get("check")
        value = fields.get(field)

        if check == "regex":
            pattern = rule.get("pattern", "")
            if value and not re.match(pattern, str(value)):
                failures.append(
                    f"{field}: value '{value}' does not match expected format"
                )
        elif check == "required":
            if not value:
                failures.append(f"{field}: required field is missing")
        elif check == "range":
            if value is not None:
                try:
                    num = float(str(value).replace(",", ""))
                    min_v = rule.get("min")
                    max_v = rule.get("max")
                    if min_v is not None and num < min_v:
                        failures.append(f"{field}: value {num} is below minimum {min_v}")
                    if max_v is not None and num > max_v:
                        failures.append(f"{field}: value {num} exceeds maximum {max_v}")
                except (ValueError, TypeError):
                    failures.append(f"{field}: could not parse as number")
        elif check == "date_not_future":
            # Date must not be in the future
            import datetime as _dt
            if value:
                from app.services.extraction_service import _parse_date
                d = _parse_date(value)
                if d and d > _dt.date.today():
                    failures.append(f"{field}: date {d} is in the future")

    return failures


# ── Cross-document consistency check ─────────────────────────────────────────

async def _check_consistency(
    db: AsyncSession,
    claim_id: str,
    doc_id: str,
    document_type_code: str,
    promoted: dict[str, Any],
) -> None:
    """Compare promoted columns of the newly extracted document against
    other existing ClaimDocuments on the same claim.
    Flags the document if any EXACT rules differ.
    """
    if not promoted:
        return

    res = await db.execute(
        select(ClaimDocument).where(
            ClaimDocument.claim_id == uuid.UUID(claim_id),
            ClaimDocument.id != uuid.UUID(doc_id),
            ClaimDocument.ocr_status == "COMPLETED",
        )
    )
    other_docs = list(res.scalars().all())
    if not other_docs:
        return

    discrepancies: list[str] = []

    for col, rule_config in CONSISTENCY_RULES.items():
        tolerance = rule_config.get("tolerance", "fuzzy")
        must_match = rule_config.get("must_match_across", [])

        if document_type_code not in must_match:
            continue
        new_val = promoted.get(col)
        if new_val is None:
            continue

        for other in other_docs:
            if other.document_type_code not in must_match:
                continue
            other_val = getattr(other, col, None)
            if other_val is None:
                continue

            if tolerance == "exact":
                if str(new_val).strip().lower() != str(other_val).strip().lower():
                    discrepancies.append(
                        f"{col}: this doc has '{new_val}' but "
                        f"{other.document_type_code} has '{other_val}'"
                    )
            elif tolerance == "fuzzy":
                # Simple fuzzy: share at least 60% of words
                new_words = set(str(new_val).lower().split())
                other_words = set(str(other_val).lower().split())
                if new_words and other_words:
                    overlap = len(new_words & other_words)
                    ratio = overlap / max(len(new_words), len(other_words))
                    if ratio < 0.4:
                        discrepancies.append(
                            f"{col}: possible mismatch — '{new_val}' vs "
                            f"'{other_val}' in {other.document_type_code}"
                        )

    if discrepancies:
        # Re-fetch the doc in this session and flag it
        doc_res = await db.execute(
            select(ClaimDocument).where(ClaimDocument.id == uuid.UUID(doc_id))
        )
        doc = doc_res.scalar_one_or_none()
        if doc:
            if doc.validation_status == "ACCEPTED":
                doc.validation_status = "FLAGGED"
            existing = doc.validation_reason or ""
            doc.validation_reason = (
                existing + ("\n" if existing else "") +
                "Cross-doc discrepancies: " + "; ".join(discrepancies)
            )
            await db.commit()
            logger.warning(
                "ClaimDocument %s consistency issues: %s", doc_id, discrepancies
            )


# ── List ──────────────────────────────────────────────────────────────────────

async def list_claim_documents(
    claim_id: str,
    requester_id: str,
    role: str,
    db: AsyncSession,
) -> list[ClaimDocument]:
    """Return all ClaimDocument rows for a claim (owner or staff)."""
    claim_res = await db.execute(select(Claim).where(Claim.id == uuid.UUID(claim_id)))
    claim = claim_res.scalar_one_or_none()
    if not claim:
        raise NotFoundError("Claim not found")
    if role == "CUSTOMER" and str(claim.user_id) != requester_id:
        raise PermissionDeniedError("Not your claim")

    res = await db.execute(
        select(ClaimDocument)
        .where(ClaimDocument.claim_id == uuid.UUID(claim_id))
        .order_by(ClaimDocument.created_at)
    )
    return list(res.scalars().all())


# ── Get raw bytes (decrypt) ───────────────────────────────────────────────────

async def get_claim_document_bytes(
    doc_id: str,
    requester_id: str,
    role: str,
    db: AsyncSession,
) -> tuple[bytes, ClaimDocument]:
    res = await db.execute(
        select(ClaimDocument).where(ClaimDocument.id == uuid.UUID(doc_id))
    )
    doc = res.scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document not found")

    if role == "CUSTOMER":
        claim_res = await db.execute(select(Claim).where(Claim.id == doc.claim_id))
        claim = claim_res.scalar_one_or_none()
        if not claim or str(claim.user_id) != requester_id:
            raise PermissionDeniedError("Not your document")

    encrypted = Path(doc.storage_path).read_bytes()
    raw = _get_fernet().decrypt(encrypted)
    return raw, doc


# ── Quick relevance check (no DB writes) ─────────────────────────────────────

async def validate_document_relevance(
    content: bytes,
    content_type: str,
    document_type_code: str,
    claim_type: str,
) -> dict[str, Any]:
    """
    Fast Gemini relevance check — no DB writes, no OCR extraction.
    Returns whether the uploaded file looks like an insurance document
    of the expected type/claim category.
    """
    prompt = f"""You are an insurance document validator.

Examine this document carefully and determine:
1. Is it genuinely related to insurance — specifically a {claim_type} insurance claim?
2. Does it match or closely match the expected document type: "{document_type_code}"?

Respond ONLY with a valid JSON object (no markdown fences):
{{
  "is_relevant": true,
  "reason": "brief 1-2 sentence explanation",
  "detected_type": "what this document actually appears to be"
}}

Set "is_relevant" to FALSE only if:
- The document is completely irrelevant to insurance (e.g. a food photo, social media screenshot, blank page, personal selfie, shopping receipt, utility bill for a health claim, etc.)
- The document clearly belongs to a different insurance domain (e.g. a motor RC book for a HEALTH claim, or a discharge summary for a MOTOR claim)

Set "is_relevant" to TRUE if it looks like a reasonable insurance document for {claim_type}, even if formatting differs or image quality is poor.
"""
    result = await _call_gemini(content, content_type, prompt)
    fields = result.get("fields", {})

    # If Gemini returned nothing, be lenient — accept for manual review
    if not fields:
        return {
            "is_relevant": True,
            "reason": "Could not automatically verify — accepted for manual review.",
            "detected_type": document_type_code,
        }

    is_relevant = fields.get("is_relevant", True)
    reason = fields.get("reason", "Document appears relevant.")
    detected_type = fields.get("detected_type", document_type_code)

    return {
        "is_relevant": bool(is_relevant),
        "reason": str(reason),
        "detected_type": str(detected_type),
    }


# ── Update extracted data (manual correction) ────────────────────────────────

async def update_claim_document_data(
    doc_id: str,
    extracted_data: dict[str, Any],
    requester_id: str,
    role: str,
    db: AsyncSession,
) -> ClaimDocument:
    """Allow a user or adjuster to manually correct the extracted fields."""
    res = await db.execute(
        select(ClaimDocument).where(ClaimDocument.id == uuid.UUID(doc_id))
    )
    doc = res.scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document not found")

    if role == "CUSTOMER":
        claim_res = await db.execute(select(Claim).where(Claim.id == doc.claim_id))
        claim = claim_res.scalar_one_or_none()
        if not claim or str(claim.user_id) != requester_id:
            raise PermissionDeniedError("Not your document")

    doc.extracted_data = extracted_data
    await db.commit()
    await db.refresh(doc)
    return doc
