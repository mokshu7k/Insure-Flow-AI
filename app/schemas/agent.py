"""Agent / conversation schemas."""
from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel


class AgentSessionResponse(BaseModel):
    session_id: str
    message: str = "Session created"


class AgentMessageRequest(BaseModel):
    message: str


class AgentMessageResponse(BaseModel):
    session_id: str
    reply: str
    intent: Optional[str] = None


class AgentVoiceResponse(BaseModel):
    session_id: str
    reply_text: str
    audio_base64: Optional[str] = None  # base64-encoded MP3 from GCP TTS
