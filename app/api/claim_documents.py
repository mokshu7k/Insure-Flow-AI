"""ClaimDocument routes — new model-aware upload, list, and download."""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response as FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from fastapi import Body
from app.schemas.claim_document import ClaimDocumentListResponse, ClaimDocumentResponse
from app.services import claim_document_service

router = APIRouter(prefix="/claim-documents", tags=["claim-documents"])


@router.post("/inline-ocr")
async def inline_ocr_preview(
    document_type_code: str = Form(...),
    claim_type: str = Form(...),
    requirement_id: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Combined relevance check + full OCR extraction in one LLM call.
    No DB writes.  Returns is_relevant, extracted_fields, confidence and
    missing_fields so the frontend can show inline results and let the user
    edit before the final upload."""
    from app.config import settings
    from app.models.document_requirement import DocumentRequirement

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="File too large")

    requirement = None
    if requirement_id:
        res = await db.execute(
            select(DocumentRequirement).where(
                DocumentRequirement.id == uuid.UUID(requirement_id)
            )
        )
        requirement = res.scalar_one_or_none()

    result = await claim_document_service.inline_ocr_preview(
        content=content,
        content_type=file.content_type or "",
        document_type_code=document_type_code,
        claim_type=claim_type,
        requirement=requirement,
    )
    return result


@router.post("", response_model=ClaimDocumentResponse, status_code=201)
async def upload_claim_document(
    background_tasks: BackgroundTasks,
    claim_id: str = Form(...),
    document_type_code: str = Form(...),
    document_requirement_id: str | None = Form(None),
    precomputed_data: str | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document for a claim.  If *precomputed_data* (JSON string) is
    provided the inline-OCR result is used directly and no background
    extraction runs.  Otherwise template-aware Gemini extraction runs in the
    background."""
    parsed_precomputed: dict | None = None
    if precomputed_data:
        try:
            parsed_precomputed = json.loads(precomputed_data)
        except (json.JSONDecodeError, ValueError):
            parsed_precomputed = None

    doc = await claim_document_service.upload_claim_document(
        claim_id=claim_id,
        uploader_id=str(current_user.id),
        role=current_user.role,
        file=file,
        document_type_code=document_type_code,
        document_requirement_id=document_requirement_id,
        db=db,
        background_tasks=background_tasks,
        precomputed_data=parsed_precomputed,
    )
    return ClaimDocumentResponse.model_validate(doc)


@router.get("", response_model=ClaimDocumentListResponse)
async def list_claim_documents(
    claim_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all ClaimDocuments for a claim (owner or staff)."""
    docs = await claim_document_service.list_claim_documents(
        claim_id=claim_id,
        requester_id=str(current_user.id),
        role=current_user.role,
        db=db,
    )
    items = [ClaimDocumentResponse.model_validate(d) for d in docs]
    return ClaimDocumentListResponse(items=items, total=len(items))


@router.patch("/{doc_id}/extracted-data", response_model=ClaimDocumentResponse)
async def update_extracted_data(
    doc_id: str,
    extracted_data: dict = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually correct the extracted fields for a claim document."""
    doc = await claim_document_service.update_claim_document_data(
        doc_id=doc_id,
        extracted_data=extracted_data,
        requester_id=str(current_user.id),
        role=current_user.role,
        db=db,
    )
    return ClaimDocumentResponse.model_validate(doc)


@router.get("/{doc_id}/download")
async def download_claim_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw_bytes, doc = await claim_document_service.get_claim_document_bytes(
        doc_id=doc_id,
        requester_id=str(current_user.id),
        role=current_user.role,
        db=db,
    )
    return FileResponse(
        content=raw_bytes,
        media_type=doc.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{doc.original_filename or doc_id}"'
        },
    )


@router.get("/{doc_id}/download-url")
async def get_document_download_url(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a short-lived signed GCS URL for admin / adjuster downloads.

    - Admins and adjusters: receive a signed URL (60-min expiry) **or** a
      fallback indicator to use the ``/download`` endpoint when GCS signed
      URLs are unavailable (e.g. ADC without signing permission).
    - Customers: receive ``403`` — they should use ``/download`` instead.
    """
    from sqlalchemy import select as _select
    from app.models.claim_document import ClaimDocument
    from fastapi import HTTPException

    # Only admins / adjusters may use the signed-URL shortcut
    if current_user.role not in ("INSURER_ADMIN", "CLAIM_ADJUSTER", "AUDITOR"):
        raise HTTPException(status_code=403, detail="Not authorised to request a signed URL")

    res = await db.execute(_select(ClaimDocument).where(ClaimDocument.id == uuid.UUID(doc_id)))
    doc = res.scalar_one_or_none()
    if not doc:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(status_code=404, detail="Document not found")

    signed_url: str | None = None
    if doc.gcs_path:
        import asyncio
        from app.services import gcs_service as _gcs_svc
        loop = asyncio.get_event_loop()
        signed_url = await loop.run_in_executor(
            None, _gcs_svc.generate_signed_url, doc.gcs_path
        )

    return {
        "doc_id": doc_id,
        "gcs_path": doc.gcs_path,
        "download_url": signed_url,
        # When signed_url is None the caller should fall back to the /download endpoint
        "fallback_endpoint": f"/api/claim-documents/{doc_id}/download",
        "original_filename": doc.original_filename,
    }
