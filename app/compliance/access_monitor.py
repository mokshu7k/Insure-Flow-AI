"""
Compliance: Access Monitor
HIPAA-aligned access logging for all document and sensitive data reads.
Every document view/download is recorded — immutably.
"""
import logging
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.models.access_log import DocumentAccessLog
from app.models.document import Document

logger = logging.getLogger(__name__)


class AccessMonitor:
    """
    Document and sensitive data access monitor.

    CRITICAL: Every read of a sensitive document MUST be logged.
    This is the HIPAA-aligned access audit trail.

    Actions tracked:
    - VIEW:     User opened/previewed a document
    - DOWNLOAD: User downloaded a document
    - UPLOAD:   User uploaded a document
    - OCR:      System processed a document via OCR
    - AI:       System used document in fraud analysis
    """

    VALID_ACTIONS = {"VIEW", "DOWNLOAD", "UPLOAD", "OCR", "AI", "DELETE_REQUEST"}

    def __init__(self, db: Session):
        self.db = db

    def log_access(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        action: str,
        metadata: Optional[dict] = None,
    ) -> DocumentAccessLog:
        """
        Record a document access event.

        Args:
            user_id: ID of user or system actor
            document_id: ID of document being accessed
            action: Action type (VIEW, DOWNLOAD, UPLOAD, OCR, AI)
            metadata: Optional additional context

        Returns:
            DocumentAccessLog record
        """
        action = action.upper()
        if action not in self.VALID_ACTIONS:
            logger.warning(f"Unknown access action: {action}. Logging anyway.")

        log_entry = DocumentAccessLog(
            id=uuid.uuid4(),
            user_id=user_id,
            document_id=document_id,
            action=action,
            timestamp=datetime.utcnow(),
        )

        self.db.add(log_entry)
        self.db.commit()

        logger.info(
            f"ACCESS_LOG: user={user_id} document={document_id} action={action}"
        )

        return log_entry

    def log_bulk_access(
        self,
        user_id: uuid.UUID,
        document_ids: list,
        action: str,
    ) -> int:
        """
        Log access to multiple documents (e.g., fraud analysis batch).

        Args:
            user_id: Actor
            document_ids: List of document UUIDs
            action: Action type

        Returns:
            Number of log entries created
        """
        action = action.upper()
        entries = []

        for doc_id in document_ids:
            entries.append(DocumentAccessLog(
                id=uuid.uuid4(),
                user_id=user_id,
                document_id=doc_id,
                action=action,
                timestamp=datetime.utcnow(),
            ))

        self.db.bulk_save_objects(entries)
        self.db.commit()

        logger.info(
            f"BULK_ACCESS_LOG: user={user_id} documents={len(document_ids)} action={action}"
        )

        return len(entries)

    def get_document_access_history(
        self,
        document_id: uuid.UUID,
        limit: int = 100,
    ) -> list:
        """
        Get full access history for a document.
        Used by auditors for document-level investigation.

        Args:
            document_id: Document UUID
            limit: Maximum records to return

        Returns:
            List of DocumentAccessLog records
        """
        return (
            self.db.query(DocumentAccessLog)
            .filter(DocumentAccessLog.document_id == document_id)
            .order_by(DocumentAccessLog.timestamp.desc())
            .limit(limit)
            .all()
        )

    def get_user_access_history(
        self,
        user_id: uuid.UUID,
        limit: int = 200,
    ) -> list:
        """
        Get full access history for a user.
        Used by compliance auditors.

        Args:
            user_id: User UUID
            limit: Maximum records to return

        Returns:
            List of DocumentAccessLog records
        """
        return (
            self.db.query(DocumentAccessLog)
            .filter(DocumentAccessLog.user_id == user_id)
            .order_by(DocumentAccessLog.timestamp.desc())
            .limit(limit)
            .all()
        )

    def detect_anomalous_access(
        self,
        user_id: uuid.UUID,
        time_window_minutes: int = 60,
        access_threshold: int = 50,
    ) -> dict:
        """
        Detect anomalously high document access rates.
        Security feature: flag potential data exfiltration.

        Args:
            user_id: User to check
            time_window_minutes: Rolling window in minutes
            access_threshold: Accesses above this = anomalous

        Returns:
            Dict with anomaly verdict
        """
        from datetime import timedelta

        window_start = datetime.utcnow() - timedelta(minutes=time_window_minutes)

        access_count = (
            self.db.query(DocumentAccessLog)
            .filter(
                DocumentAccessLog.user_id == user_id,
                DocumentAccessLog.timestamp >= window_start,
            )
            .count()
        )

        is_anomalous = access_count > access_threshold

        if is_anomalous:
            logger.warning(
                f"ANOMALOUS_ACCESS: user={user_id} accessed {access_count} documents "
                f"in {time_window_minutes} minutes (threshold={access_threshold})"
            )

        return {
            "user_id": str(user_id),
            "access_count": access_count,
            "time_window_minutes": time_window_minutes,
            "threshold": access_threshold,
            "is_anomalous": is_anomalous,
            "checked_at": datetime.utcnow().isoformat(),
        }