"""
User model
"""
from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class User(BaseModel):
    """
    User entity
    Supports multiple roles: CUSTOMER, PROVIDER, INSURER_ADMIN, AUDITOR
    """
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # CUSTOMER, PROVIDER, INSURER_ADMIN, AUDITOR
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    consents = relationship("UserConsent", back_populates="user", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="user", foreign_keys="Claim.user_id")
    
    def __repr__(self):
        return f"<User {self.email} ({self.role})>"