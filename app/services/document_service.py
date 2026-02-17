"""
Document Service
Upload → encrypt → OCR → store → log access.
The only place in the codebase that touches raw file bytes.
"""
import logging
import uuid
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.document import Document
from app.ocr.pipeline import OCRPipeline
from app.utils.file_storage import FileStorageService
from app.compliance.access_monitor import AccessMonitor
from app.services.audit_service import AuditService
from app.core.constants import AuditAction
from app.core.exceptions import DocumentNotFoundException, ClaimNotFoundException

logger = logging.getLogger(__name__)

# MIME types that support OCR
OCR_SUPPORTED_MIME = {
    "image/jpeg", "image/jpg", "image/png",
    "image/tiff", "image/bmp", "application/pdf",
}

VALID_DOCUMENT_TYPES = {
    "INVOICE", "PRESCRIPTION", "MEDICAL_REPORT",
    "DISCHARGE_SUMMARY", "POLICE_REPORT", "VEHICLE_RC",
    "ESTIMATE", "OTHER",
}


class DocumentService:

    def __init__(self, db: Session):
        self.db = db
        self.file_storage = FileStorageService()
        self.ocr = OCRPipeline()
        self.access_monitor = AccessMonitor(db)
        self.audit = AuditService(db)

    # ── Upload ────────────────────────────────────────────────────────────────

    def upload_document(
        self,
        claim_id: uuid.UUID,
        file_bytes: bytes,
        content_type: str,
        document_type: str,
        uploader_id: uuid.UUID,
        original_filename: str = "document",
    ) -> Document:
        """
        Validate → encrypt-store → OCR → create DB record → log.

        Args:
            claim_id:          Owning claim UUID.
            file_bytes:        Raw upload bytes.
            content_type:      MIME type from multipart header.
            document_type:     One of VALID_DOCUMENT_TYPES.
            uploader_id:       Acting user UUID (for audit/access logs).
            original_filename: Filename from upload (used for extension hint).

        Returns:
            Persisted Document record.
        """
        # Validate document_type
        if document_type not in VALID_DOCUMENT_TYPES:
            document_type = "OTHER"

        # Confirm claim exists
        claim = self.db.query(Claim).filter(Claim.id == claim_id).first()
        if not claim:
            raise ClaimNotFoundException(str(claim_id))

        # 1. Encrypt and store file
        storage_ref = self.file_storage.store_document(
            file_bytes=file_bytes,
            content_type=content_type,
            claim_id=str(claim_id),
            original_filename=original_filename,
        )

        # 2. OCR — pass content_type so pipeline can route correctly
        ocr_result: Optional[dict] = None
        if content_type in OCR_SUPPORTED_MIME:
            # pipeline.process never raises — returns manual_review=True on error
            ocr_result = self.ocr.process(
                file_bytes=file_bytes,
                content_type=content_type,
                document_type=document_type,
            )
            logger.info(
                f"OCR for claim={claim_id}: "
                f"confidence={ocr_result.get('confidence', 0):.2f} "
                f"manual_review={ocr_result.get('requires_manual_review')}"
            )

        # 3. Persist document record
        document = Document(
            id=uuid.uuid4(),
            claim_id=claim_id,
            file_path=storage_ref,
            document_type=document_type,
            ocr_extracted_json=ocr_result,
        )
        self.db.add(document)

        # 4. Advance claim status if still at SUBMITTED
        if claim.status == "SUBMITTED":
            claim.status = "OCR_PROCESSED"

        self.db.commit()
        self.db.refresh(document)

        # 5. Compliance logs (after commit so document.id is persisted)
        self.access_monitor.log_access(
            user_id=uploader_id,
            document_id=document.id,
            action="UPLOAD",
        )
        self.audit.log_action(
            actor_id=uploader_id,
            action_type=AuditAction.DOCUMENT_UPLOADED,
            entity_type="DOCUMENT",
            entity_id=document.id,
            metadata={
                "claim_id": str(claim_id),
                "document_type": document_type,
                "ocr_confidence": ocr_result.get("confidence") if ocr_result else None,
                "requires_manual_review": (
                    ocr_result.get("requires_manual_review") if ocr_result else False
                ),
            },
        )

        return document

    # ── Retrieve ──────────────────────────────────────────────────────────────

    def get_document(
        self,
        document_id: uuid.UUID,
        requester_id: uuid.UUID,
    ) -> Tuple[Document, bytes]:
        """Return (Document, decrypted_bytes) and log access."""
        doc = self._fetch_or_raise(document_id)
        file_bytes = self.file_storage.retrieve_document(doc.file_path)

        self.access_monitor.log_access(
            user_id=requester_id,
            document_id=document_id,
            action="VIEW",
        )
        self.audit.log_action(
            actor_id=requester_id,
            action_type=AuditAction.DOCUMENT_ACCESSED,
            entity_type="DOCUMENT",
            entity_id=document_id,
        )
        return doc, file_bytes

    def get_claim_documents(self, claim_id: uuid.UUID) -> List[Document]:
        return (
            self.db.query(Document)
            .filter(Document.claim_id == claim_id)
            .order_by(Document.created_at.desc())
            .all()
        )

    def get_ocr_result(self, document_id: uuid.UUID) -> Optional[dict]:
        doc = self._fetch_or_raise(document_id)
        return doc.ocr_extracted_json

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fetch_or_raise(self, document_id: uuid.UUID) -> Document:
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise DocumentNotFoundException(str(document_id))
        return doc