"""
Document Access Log model (HIPAA-aligned)
"""
from sqlalchemy import Column, String, ForeignKey, DateTime
from datetime import datetime
import uuid

from app.models.base import Base, GUID


class DocumentAccessLog(Base):
    """
    Document access tracking (HIPAA-aligned)
    Immutable - no updates/deletes
    """
    __tablename__ = "document_access_logs"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    document_id = Column(GUID(), ForeignKey("documents.id"), nullable=False, index=True)
    
    # Action: VIEW, DOWNLOAD, UPLOAD
    action = Column(String(50), nullable=False)
    
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<DocumentAccessLog user={self.user_id} doc={self.document_id} action={self.action}>"