"""
Audit Log model (Immutable)
"""
from sqlalchemy import Column, String, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.models.base import Base  # Not BaseModel - we don't want updated_at


class AuditLog(Base):
    """
    Immutable audit log
    CRITICAL: No UPDATE or DELETE operations allowed
    """
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    
    # Actor (who performed the action)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    
    # Action type (USER_CREATED, CLAIM_SUBMITTED, etc.)
    action_type = Column(String(100), nullable=False, index=True)
    
    # Entity affected
    entity_type = Column(String(100), nullable=False)  # USER, CLAIM, DOCUMENT, etc.
    entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Additional metadata (JSON)
    metadata_json = Column(JSON, nullable=True)
    
    # Timestamp (immutable)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<AuditLog {self.action_type} by {self.actor_id} at {self.timestamp}>"