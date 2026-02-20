"""Agent / conversation schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

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


class ChatMessage(BaseModel):
    role: str        # "human" | "ai"
    content: str


class ChatSessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_message: Optional[str] = None  # preview of last AI reply


class ChatSessionDetail(BaseModel):
    session_id: str
    title: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    messages: List[ChatMessage]


class RenameChatRequest(BaseModel):
    title: str
