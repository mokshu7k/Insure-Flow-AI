"""
Agent routes — text conversation and voice (GCP TTS/STT).
LangGraph state is loaded/saved per session_id from DB.

Memory strategy: sliding window — we persist all messages to DB but only
feed the last MEMORY_WINDOW messages into the graph each turn.
"""
from __future__ import annotations

import base64
import json
import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_agents.agent.gcp_voice import audio_to_base64, synthesize_speech, transcribe_audio
from app.ai_agents.agent.graph import agent_graph
from app.db.session import get_db, AsyncSessionLocal
from app.dependencies import get_current_user
from app.models.agent_session import AgentSession
from app.models.user import User
from app.schemas.agent import (
    AgentMessageRequest,
    AgentMessageResponse,
    AgentSessionResponse,
    AgentVoiceResponse,
    ChatMessage,
    ChatSessionDetail,
    ChatSessionSummary,
    RenameChatRequest,
)

# ---------------------------------------------------------------------------
# How many saved messages to pass into the graph as memory (sliding window).
# 10 = ~5 back-and-forth exchanges.
# ---------------------------------------------------------------------------
MEMORY_WINDOW = 10


def _content_str(content: Any) -> str:
    """Normalise Gemini content (str or list-of-blocks) to a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return " ".join(p for p in parts if p)
    return str(content) if content is not None else ""


def _derive_title(messages: list[dict]) -> str:
    """Generate a short title from the first human message in the session."""
    for m in messages:
        if m.get("role") in ("human", "user"):
            text = _content_str(m.get("content", "")).strip()
            if text:
                if len(text) > 50:
                    text = text[:50].rsplit(" ", 1)[0] + "\u2026"
                return text
    return "New conversation"


def _last_ai_preview(messages: list[dict]) -> str | None:
    """Return a short preview of the last AI message."""
    for m in reversed(messages):
        if m.get("role") in ("ai", "assistant"):
            text = _content_str(m.get("content", "")).strip()
            if text:
                if len(text) > 80:
                    text = text[:80].rsplit(" ", 1)[0] + "\u2026"
                return text
    return None


router = APIRouter(prefix="/agent", tags=["agent"])


async def _get_or_create_session(session_id: str | None, user_id: str, db: AsyncSession) -> AgentSession:
    if session_id:
        result = await db.execute(
            select(AgentSession).where(
                AgentSession.session_id == session_id,
                AgentSession.user_id == uuid.UUID(user_id),
            )
        )
        session = result.scalar_one_or_none()
        if session:
            return session
    # Create new
    now = datetime.now(tz=timezone.utc)
    sid = session_id or secrets.token_hex(16)
    session = AgentSession(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        session_id=sid,
        title="New conversation",
        graph_state={},
        created_at=now,
        updated_at=now,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# List all sessions for the current user
# ---------------------------------------------------------------------------
@router.get("/sessions", response_model=List[ChatSessionSummary])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentSession)
        .where(AgentSession.user_id == current_user.id)
        .order_by(desc(AgentSession.updated_at))
    )
    sessions = result.scalars().all()
    return [
        ChatSessionSummary(
            session_id=s.session_id,
            title=s.title or "New conversation",
            created_at=s.created_at,
            updated_at=s.updated_at,
            last_message=_last_ai_preview(s.graph_state.get("messages", [])),
        )
        for s in sessions
    ]


# ---------------------------------------------------------------------------
# Get full conversation history for a session
# ---------------------------------------------------------------------------
@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.session_id == session_id,
            AgentSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = [
        ChatMessage(role=m.get("role", "human"), content=m.get("content", ""))
        for m in session.graph_state.get("messages", [])
        if m.get("content", "").strip()
    ]
    return ChatSessionDetail(
        session_id=session.session_id,
        title=session.title or "New conversation",
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=messages,
    )


# ---------------------------------------------------------------------------
# Rename a session
# ---------------------------------------------------------------------------
@router.patch("/sessions/{session_id}", response_model=ChatSessionSummary)
async def rename_session(
    session_id: str,
    payload: RenameChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.session_id == session_id,
            AgentSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.title = payload.title.strip()[:200]
    await db.commit()
    return ChatSessionSummary(
        session_id=session.session_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_message=_last_ai_preview(session.graph_state.get("messages", [])),
    )


# ---------------------------------------------------------------------------
# Delete a session
# ---------------------------------------------------------------------------
@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.session_id == session_id,
            AgentSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()


# ---------------------------------------------------------------------------
# Create a new blank session
# ---------------------------------------------------------------------------
@router.post("/sessions", response_model=AgentSessionResponse)
async def create_session(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await _get_or_create_session(None, str(current_user.id), db)
    return AgentSessionResponse(session_id=session.session_id)


@router.post("/sessions/{session_id}/message", response_model=AgentMessageResponse)
async def send_message(
    session_id: str,
    payload: AgentMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await _get_or_create_session(session_id, str(current_user.id), db)

    # ── Load history with sliding window ──────────────────────────────────────
    saved_messages_raw = session.graph_state.get("messages", [])

    # Apply sliding window: keep only last MEMORY_WINDOW saved messages
    windowed_raw = saved_messages_raw[-MEMORY_WINDOW:]

    from langchain_core.messages import AIMessage
    saved_messages = []
    for msg in windowed_raw:
        role = msg.get("role", "human")
        content = msg.get("content", "")
        if role in ("ai", "assistant"):
            saved_messages.append(AIMessage(content=content))
        else:
            saved_messages.append(HumanMessage(content=content))

    state = {
        "messages": saved_messages + [HumanMessage(content=payload.message)],
        "user_id": str(current_user.id),
        "session_id": session_id,
        "intent": None,
        "route": None,
        "supervisor_notes": None,
        "data_context": None,
        # Pass the session FACTORY, not the request db — tools open their own
        # isolated sessions so they are never affected by the request transaction.
        "context": {"db_factory": AsyncSessionLocal},
        "last_tool_result": None,
    }

    result_state = await agent_graph.ainvoke(state)

    # ── Persist full history (append new messages to *all* saved, not just window) ──
    new_messages = result_state.get("messages", [])
    # Combine all previously saved + new, then persist
    combined_raw = saved_messages_raw + [HumanMessage(content=payload.message)] + [
        m for m in new_messages if m not in saved_messages
    ]
    serializable_messages = []
    for m in combined_raw:
        content = _content_str(getattr(m, "content", ""))
        role = getattr(m, "type", "human")
        serializable_messages.append({"role": role, "content": content})

    # Auto-title on first real message
    if session.title in (None, "New conversation") and serializable_messages:
        session.title = _derive_title(serializable_messages)

    session.graph_state = {"messages": serializable_messages}
    session.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()

    # ── Extract last AI reply ─────────────────────────────────────────────────
    last_reply = ""
    for m in reversed(result_state.get("messages", [])):
        role = getattr(m, "type", None) or m.get("role", "") if isinstance(m, dict) else getattr(m, "type", "")
        if role in ("ai", "assistant"):
            raw_reply = _content_str(getattr(m, "content", m.get("content", "") if isinstance(m, dict) else ""))
            # Sanitize: remove Thinking markers and special characters
            last_reply = re.sub(r'\[?Thinking[:\s]*[^\]]*\]?', '', raw_reply)  # Remove [Thinking] markers
            last_reply = re.sub(r'<thinking>[\s\S]*?</thinking>', '', last_reply)  # Remove <thinking> tags
            last_reply = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', last_reply)  # Remove control chars
            last_reply = re.sub(r'\n\s*\n', '\n', last_reply)  # Clean newlines
            last_reply = last_reply.strip()
            break

    return AgentMessageResponse(
        session_id=session_id,
        reply=last_reply,
        intent=result_state.get("intent"),
    )


@router.post("/sessions/{session_id}/voice", response_model=AgentVoiceResponse)
async def send_voice(
    session_id: str,
    audio: UploadFile = File(..., description="Audio file (WEBM/OGG/WAV) from browser"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # STT
    audio_bytes = await audio.read()
    text = await transcribe_audio(audio_bytes)
    if not text:
        text = "(Could not transcribe audio. Please try again or type your message.)"

    # Route through the same text agent
    session = await _get_or_create_session(session_id, str(current_user.id), db)

    from langchain_core.messages import AIMessage
    saved_messages_raw = session.graph_state.get("messages", [])
    windowed_raw = saved_messages_raw[-MEMORY_WINDOW:]

    saved_messages = []
    for msg in windowed_raw:
        role = msg.get("role", "human")
        content = msg.get("content", "")
        if role in ("ai", "assistant"):
            saved_messages.append(AIMessage(content=content))
        else:
            saved_messages.append(HumanMessage(content=content))

    state = {
        "messages": saved_messages + [HumanMessage(content=text)],
        "user_id": str(current_user.id),
        "session_id": session_id,
        "intent": None,
        "route": None,
        "supervisor_notes": None,
        "data_context": None,
        "context": {"db_factory": AsyncSessionLocal},
        "last_tool_result": None,
    }
    result_state = await agent_graph.ainvoke(state)

    # Persist
    new_messages = result_state.get("messages", [])
    combined_raw = saved_messages_raw + [HumanMessage(content=text)] + [
        m for m in new_messages if m not in saved_messages
    ]
    serializable_messages = [
        {"role": getattr(m, "type", "human"), "content": _content_str(getattr(m, "content", ""))}
        for m in combined_raw
    ]
    # Auto-title on first real message (voice)
    if session.title in (None, "New conversation") and serializable_messages:
        session.title = _derive_title(serializable_messages)

    session.graph_state = {"messages": serializable_messages}
    session.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()

    last_reply = ""
    for m in reversed(result_state.get("messages", [])):
        role = getattr(m, "type", "") if not isinstance(m, dict) else m.get("role", "")
        if role in ("ai", "assistant"):
            last_reply = _content_str(getattr(m, "content", "") if not isinstance(m, dict) else m.get("content", ""))
            break

    # TTS
    audio_out = await synthesize_speech(last_reply)
    audio_b64 = audio_to_base64(audio_out) if audio_out else None

    return AgentVoiceResponse(session_id=session_id, reply_text=last_reply, audio_base64=audio_b64)
