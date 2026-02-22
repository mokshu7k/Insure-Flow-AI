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
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.dependencies import get_current_user
from app.models.user import User
from app.ai_agents.agent.gcp_voice import transcribe_audio as gcp_transcribe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/speech", tags=["speech"])

LANGUAGE_MAP = {
    "en": "en-IN",
    "hi": "hi-IN",
    "mr": "mr-IN",
}


class TranscriptionResponse(BaseModel):
    text: str
    method: str = "unknown"


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form("en"),
    current_user: User = Depends(get_current_user),
) -> TranscriptionResponse:
    """
    Accept a recorded audio blob and return the transcribed text.
    Tries GCP Cloud Speech-to-Text first; falls back to Gemini if unavailable.
    """
    lang_code = LANGUAGE_MAP.get(language, "en-IN")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio too large (max 25 MB)")

    # ── Attempt 1: GCP Cloud Speech-to-Text ──────────────────────────────────
    try:
        text = await gcp_transcribe(content, language_code=lang_code)
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
        from google import genai
        from google.genai import types as _genai_types
        client = genai.Client(api_key=settings.GCP_API_KEY)

        audio_part = _genai_types.Part.from_bytes(data=content, mime_type=mime)
        lang_label = {"en-IN": "English", "hi-IN": "Hindi", "mr-IN": "Marathi"}.get(lang_code, "English")
        prompt = (
            f"Transcribe the speech in this audio recording exactly as spoken in {lang_label}. "
            "Return ONLY the transcribed text with no labels or commentary. "
            "If the audio is silent or inaudible, return an empty string."
        )

        def _call() -> str:
            return (client.models.generate_content(model="gemini-2.5-flash", contents=[audio_part, prompt]).text or "").strip()

        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, _call)
        logger.info("STT via Gemini (%d chars)", len(text))
        return TranscriptionResponse(text=text, method="gemini")

    except Exception as exc:
        logger.error("Gemini STT also failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")
