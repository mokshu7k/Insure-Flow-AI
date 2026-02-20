"""Document schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ExtractionResult(BaseModel):
    fields: dict[str, Any] = {}
    raw_text: Optional[str] = None
    confidence: float = 0.0
    extraction_method: str = "none"


class DocumentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    claim_id: uuid.UUID
    document_type: str
    original_filename: Optional[str]
    content_type: Optional[str]
    extracted_data: Optional[dict]
    extraction_confidence: Optional[float]
    requires_manual_review: bool
    created_at: datetime


class UpdateExtractedDataRequest(BaseModel):
    """Update extracted data for a document."""
    extracted_data: dict[str, Any]
    requires_manual_review: Optional[bool] = None
