"""
Document model
"""
from sqlalchemy import Column, String, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Document(BaseModel):
    """
    Document entity
    Stores encrypted references to uploaded files
    OCR results stored as JSON
    """
    __tablename__ = "documents"
    
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)  # Encrypted storage reference
    document_type = Column(String(50), nullable=False)  # INVOICE, PRESCRIPTION, etc.
    
    # OCR extracted data (structured JSON)
    ocr_extracted_json = Column(JSON, nullable=True)
    
    # Relationship
    claim = relationship("Claim", back_populates="documents")
    
    def __repr__(self):
        return f"<Document {self.id} type={self.document_type}>"