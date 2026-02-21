"""ClaimDocument routes — new model-aware upload, list, and download."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response as FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from fastapi import Body
from app.schemas.claim_document import ClaimDocumentListResponse, ClaimDocumentResponse
from app.services import claim_document_service

router = APIRouter(prefix="/claim-documents", tags=["claim-documents"])


@router.post("/validate-relevance")
async def validate_document_relevance(
    document_type_code: str = Form(...),
    claim_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Quick relevance check — no DB writes, no OCR.
    Returns whether the uploaded file looks like an insurance document
    of the expected type before the full upload+OCR pipeline runs."""
    from app.config import settings

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="File too large")

    result = await claim_document_service.validate_document_relevance(
        content=content,
        content_type=file.content_type or "",
        document_type_code=document_type_code,
        claim_type=claim_type,
    )
    return result


@router.post("", response_model=ClaimDocumentResponse, status_code=201)
async def upload_claim_document(
    background_tasks: BackgroundTasks,
    claim_id: str = Form(...),
    document_type_code: str = Form(...),
    document_requirement_id: str | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document for a claim.  Uses the new ClaimDocument model and
    template-aware Gemini extraction.  Extraction runs in the background."""
    doc = await claim_document_service.upload_claim_document(
        claim_id=claim_id,
        uploader_id=str(current_user.id),
        role=current_user.role,
        file=file,
        document_type_code=document_type_code,
        document_requirement_id=document_requirement_id,
        db=db,
        background_tasks=background_tasks,
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
