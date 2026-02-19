"""
User Consent model (DPDP compliance)
"""
from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import BaseModel, GUID


class UserConsent(BaseModel):
    """
    User consent tracking (DPDP Act compliance)
    Immutable once created - no updates/deletes
    """
    __tablename__ = "user_consents"
    
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    consent_version = Column(String(50), nullable=False)  # e.g., "1.0", "2.0"
    consent_text_hash = Column(String(64), nullable=False)  # SHA-256 hash of consent text
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="consents")
    
    def __repr__(self):
        return f"<UserConsent user={self.user_id} version={self.consent_version}>"