"""Document routes — upload and download."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response as FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.document import DocumentResponse, UpdateExtractedDataRequest
from app.services import document_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    claim_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all documents for a claim (owner or admin)."""
    docs = await document_service.list_documents(
        claim_id=claim_id,
        requester_id=str(current_user.id),
        role=current_user.role,
        db=db,
    )
    return docs


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    claim_id: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await document_service.upload_document(
        claim_id=claim_id,
        uploader_id=str(current_user.id),
        role=current_user.role,
        file=file,
        document_type=document_type,
        db=db,
        background_tasks=background_tasks,
    )
    return doc


@router.patch("/{document_id}/extracted-data", response_model=DocumentResponse)
async def update_extracted_data(
    document_id: str,
    payload: UpdateExtractedDataRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update extracted data for a document (owner or admin)."""
    doc = await document_service.update_extracted_data(
        document_id=document_id,
        extracted_data=payload.extracted_data,
        requires_manual_review=payload.requires_manual_review,
        requester_id=str(current_user.id),
        role=current_user.role,
        db=db,
    )
    return doc


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw_bytes, doc = await document_service.get_document_bytes(
        document_id=document_id,
        requester_id=str(current_user.id),
        role=current_user.role,
        db=db,
    )
    return FileResponse(
        content=raw_bytes,
        media_type=doc.content_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={doc.original_filename or 'document'}"},
    )
