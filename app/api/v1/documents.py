"""
Documents API Routes
All paths are under /documents.
Upload is POST /documents/{claim_id}/upload
List is   GET  /documents/claim/{claim_id}
Download is GET /documents/{document_id}/download
OCR is    GET  /documents/{document_id}/ocr
"""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.core.rbac import require_any_role, Role
from app.core.exceptions import DocumentNotFoundException, ClaimNotFoundException
from app.services.document_service import DocumentService
from app.schemas.document import DocumentResponse

router = APIRouter()

VALID_DOC_TYPES = {
    "INVOICE", "PRESCRIPTION", "MEDICAL_REPORT",
    "DISCHARGE_SUMMARY", "POLICE_REPORT", "VEHICLE_RC",
    "ESTIMATE", "OTHER",
}


@router.post("/{claim_id}/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    claim_id: str,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload and OCR-process a document for a claim.

    - Images (JPEG, PNG) and PDFs are OCR-processed automatically.
    - File is encrypted at rest.
    - Access is logged for compliance.
    """
    if document_type.upper() not in VALID_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid document_type. Must be one of: {sorted(VALID_DOC_TYPES)}",
        )

    file_bytes = await file.read()
    content_type = file.content_type or "application/octet-stream"

    svc = DocumentService(db)
    try:
        doc = svc.upload_document(
            claim_id=uuid.UUID(claim_id),
            file_bytes=file_bytes,
            content_type=content_type,
            document_type=document_type.upper(),
            uploader_id=current_user.id,
            original_filename=file.filename or "upload",
        )
    except ClaimNotFoundException:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    return DocumentResponse.from_orm(doc)


@router.get("/claim/{claim_id}", response_model=List[DocumentResponse])
def list_claim_documents(
    claim_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all documents attached to a claim."""
    svc = DocumentService(db)
    docs = svc.get_claim_documents(uuid.UUID(claim_id))
    return [DocumentResponse.from_orm(d) for d in docs]


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download (decrypt and stream) a document.
    Access logged for HIPAA compliance.
    """
    svc = DocumentService(db)
    try:
        doc, file_bytes = svc.get_document(
            document_id=uuid.UUID(document_id),
            requester_id=current_user.id,
        )
    except DocumentNotFoundException:
        raise HTTPException(status_code=404, detail="Document not found")

    content_type = "application/octet-stream"
    if doc.file_path.endswith(".pdf"):
        content_type = "application/pdf"
    elif doc.file_path.endswith((".jpg", ".jpeg")):
        content_type = "image/jpeg"
    elif doc.file_path.endswith(".png"):
        content_type = "image/png"

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename=document_{document_id}"
        },
    )


@router.get("/{document_id}/ocr")
def get_ocr_result(
    document_id: str,
    current_user: User = Depends(
        require_any_role([Role.INSURER_ADMIN, Role.AUDITOR])
    ),
    db: Session = Depends(get_db),
):
    """
    Return OCR extraction JSON for a document.
    Requires INSURER_ADMIN or AUDITOR.
    """
    svc = DocumentService(db)
    try:
        ocr_data = svc.get_ocr_result(uuid.UUID(document_id))
    except DocumentNotFoundException:
        raise HTTPException(status_code=404, detail="Document not found")

    if ocr_data is None:
        return {"message": "No OCR data available for this document"}

    return ocr_data