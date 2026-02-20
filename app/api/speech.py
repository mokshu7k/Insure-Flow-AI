"""
Speech-to-text endpoint.
Strategy:
  1. Try GCP Cloud Speech-to-Text via gcp_voice.transcribe_audio()
     (requires Application Default Credentials / service account)
  2. Fall back to Gemini multimodal transcription using GCP_API_KEY
     (always available since the same key powers document extraction)
"""
from __future__ import annotations

import asyncio
import base64
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.dependencies import get_current_user
from app.models.user import User
from app.ai_agents.agent.gcp_voice import transcribe_audio as gcp_transcribe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/speech", tags=["speech"])


class TranscriptionResponse(BaseModel):
    text: str
    method: str = "unknown"


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> TranscriptionResponse:
    """
    Accept a recorded audio blob and return the transcribed text.
    Tries GCP Cloud Speech-to-Text first; falls back to Gemini if unavailable.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio too large (max 25 MB)")

    # ── Attempt 1: GCP Cloud Speech-to-Text ──────────────────────────────────
    try:
        text = await gcp_transcribe(content, language_code="en-IN")
        if text:
            logger.info("STT via GCP Cloud Speech (%d chars)", len(text))
            return TranscriptionResponse(text=text, method="gcp-speech")
    except Exception as exc:
        logger.warning("GCP STT unavailable, falling back to Gemini: %s", exc)

    # ── Attempt 2: Gemini multimodal transcription ────────────────────────────
    raw_mime = (file.content_type or "audio/webm").split(";")[0].strip().lower()
    mime_map = {
        "audio/webm": "audio/webm", "audio/ogg": "audio/ogg",
        "audio/mp4": "audio/mp4",   "audio/mpeg": "audio/mpeg",
        "audio/wav": "audio/wav",   "audio/x-wav": "audio/wav",
    }
    mime = mime_map.get(raw_mime, "audio/webm")

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GCP_API_KEY)
        model = genai.GenerativeModel("models/gemini-2.5-flash")

        blob_b64 = base64.standard_b64encode(content).decode()
        audio_part = {"inline_data": {"mime_type": mime, "data": blob_b64}}
        prompt = (
            "Transcribe the speech in this audio recording exactly as spoken. "
            "Return ONLY the transcribed text with no labels or commentary. "
            "If the audio is silent or inaudible, return an empty string."
        )

        def _call() -> str:
            return (model.generate_content([audio_part, prompt]).text or "").strip()

        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, _call)
        logger.info("STT via Gemini (%d chars)", len(text))
        return TranscriptionResponse(text=text, method="gemini")

    except Exception as exc:
        logger.error("Gemini STT also failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")
