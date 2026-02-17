"""
Document Access Log model (HIPAA-aligned)
"""
from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.models.base import Base


class DocumentAccessLog(Base):
    """
    Document access tracking (HIPAA-aligned)
    Immutable - no updates/deletes
    """
    __tablename__ = "document_access_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    
    # Action: VIEW, DOWNLOAD, UPLOAD
    action = Column(String(50), nullable=False)
    
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<DocumentAccessLog user={self.user_id} doc={self.document_id} action={self.action}>"