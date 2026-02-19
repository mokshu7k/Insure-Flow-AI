"""
Document model
"""
from sqlalchemy import Column, String, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, GUID


class Document(BaseModel):
    """
    Document entity
    Stores encrypted references to uploaded files
    OCR results stored as JSON
    """
    __tablename__ = "documents"
    
    claim_id = Column(GUID(), ForeignKey("claims.id"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)  # Encrypted storage reference
    document_type = Column(String(50), nullable=False)  # INVOICE, PRESCRIPTION, etc.
    
    # OCR extracted data (structured JSON)
    ocr_extracted_json = Column(JSON, nullable=True)
    
    # Relationship
    claim = relationship("Claim", back_populates="documents")
    
    def __repr__(self):
        return f"<Document {self.id} type={self.document_type}>"