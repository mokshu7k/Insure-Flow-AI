"""
Audit Service
Immutable audit logging for compliance
"""
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import uuid
from datetime import datetime

from app.models.audit import AuditLog
from app.core.constants import AuditAction
from app.core.logging import get_audit_logger

audit_logger = get_audit_logger()


class AuditService:
    """
    Audit service for compliance tracking
    CRITICAL: All logs are immutable (no updates/deletes)
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_action(
        self,
        action_type: AuditAction,
        entity_type: str,
        entity_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """
        Create immutable audit log entry
        
        Args:
            action_type: Type of action (from AuditAction enum)
            entity_type: Type of entity (USER, CLAIM, DOCUMENT, etc.)
            entity_id: ID of affected entity
            actor_id: ID of user who performed action
            metadata: Additional context as JSON
        """
        audit_entry = AuditLog(
            id=uuid.uuid4(),
            actor_id=actor_id,
            action_type=action_type.value,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
            timestamp=datetime.utcnow()
        )
        
        self.db.add(audit_entry)
        self.db.commit()
        
        # Also log to audit file
        audit_logger.info(
            f"action={action_type.value} entity={entity_type} "
            f"entity_id={entity_id} actor={actor_id}"
        )
        
        return audit_entry
    
    def get_audit_trail(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        limit: int = 100
    ):
        """
        Retrieve audit trail (read-only)
        """
        query = self.db.query(AuditLog)
        
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        if entity_id:
            query = query.filter(AuditLog.entity_id == entity_id)
        if actor_id:
            query = query.filter(AuditLog.actor_id == actor_id)
        
        return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()