"""
Document schemas (Pydantic v2)
"""
from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class DocumentResponse(BaseModel):
    id: str
    claim_id: str
    document_type: str
    has_ocr_data: bool
    ocr_confidence: Optional[float] = None
    requires_manual_review: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj) -> "DocumentResponse":
        ocr = obj.ocr_extracted_json or {}
        return cls(
            id=str(obj.id),
            claim_id=str(obj.claim_id),
            document_type=obj.document_type,
            has_ocr_data=obj.ocr_extracted_json is not None,
            ocr_confidence=ocr.get("confidence"),
            requires_manual_review=ocr.get("requires_manual_review", False),
            created_at=obj.created_at,
        )


class OCRResultResponse(BaseModel):
    extracted_fields: Dict[str, Any]
    raw_text: str
    confidence: float
    requires_manual_review: bool
    ocr_metadata: Dict[str, Any]