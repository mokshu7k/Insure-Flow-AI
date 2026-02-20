"""
Agent routes — text conversation and voice (GCP TTS/STT).
LangGraph state is loaded/saved per session_id from DB.
"""
from __future__ import annotations

import base64
import json
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, UploadFile
from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_agents.agent.gcp_voice import audio_to_base64, synthesize_speech, transcribe_audio
from app.ai_agents.agent.graph import agent_graph
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.agent_session import AgentSession
from app.models.user import User
from app.schemas.agent import AgentMessageRequest, AgentMessageResponse, AgentSessionResponse, AgentVoiceResponse

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
    sid = session_id or secrets.token_hex(16)
    session = AgentSession(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        session_id=sid,
        graph_state={},
        updated_at=datetime.now(tz=timezone.utc),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


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
    # Restore + extend state
    saved_messages_raw = session.graph_state.get("messages", [])
    
    # Convert saved dict messages back to LangChain Message objects
    from langchain_core.messages import AIMessage
    saved_messages = []
    for msg in saved_messages_raw:
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
        "context": {"db": db},
        "last_tool_result": None,
    }
    result_state = await agent_graph.ainvoke(state)
    # Persist updated state (without db object — not serializable)
    serializable_messages = [
        {"role": m.type if hasattr(m, "type") else "human", "content": m.content}
        for m in result_state.get("messages", [])
    ]
    session.graph_state = {"messages": serializable_messages}
    session.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()

    # Get last assistant reply
    last_reply = ""
    for m in reversed(result_state.get("messages", [])):
        content = m.content if hasattr(m, "content") else m.get("content", "")
        role = m.type if hasattr(m, "type") else m.get("role", "")
        if role in ("ai", "assistant"):
            last_reply = content
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
    
    # Convert saved dict messages back to LangChain Message objects
    from langchain_core.messages import AIMessage
    saved_messages_raw = session.graph_state.get("messages", [])
    saved_messages = []
    for msg in saved_messages_raw:
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
        "context": {"db": db},
        "last_tool_result": None,
    }
    result_state = await agent_graph.ainvoke(state)

    last_reply = ""
    for m in reversed(result_state.get("messages", [])):
        content = m.content if hasattr(m, "content") else m.get("content", "")
        role = m.type if hasattr(m, "type") else m.get("role", "")
        if role in ("ai", "assistant"):
            last_reply = content
            break

    # TTS
    audio_out = await synthesize_speech(last_reply)
    audio_b64 = audio_to_base64(audio_out) if audio_out else None

    return AgentVoiceResponse(session_id=session_id, reply_text=last_reply, audio_base64=audio_b64)
