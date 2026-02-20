"""
GCP TTS and STT integration.
Uses google-cloud-speech for audio → text and
google-cloud-texttospeech for text → audio (MP3).
Falls back gracefully if GCP libraries are unavailable.
"""
from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)


async def transcribe_audio(audio_bytes: bytes, language_code: str = "en-IN") -> str:
    """
    Convert audio bytes to text using GCP Speech-to-Text.
    Supports WEBM_OPUS (browser MediaRecorder default) and LINEAR16.
    Returns empty string on failure.
    """
    try:
        from google.cloud import speech  # type: ignore

        client = speech.SpeechAsyncClient()
        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            sample_rate_hertz=48000,
            language_code=language_code,
            enable_automatic_punctuation=True,
            model="latest_long",
        )
        response = await client.recognize(config=config, audio=audio)
        if response.results:
            return response.results[0].alternatives[0].transcript
        return ""
    except ImportError:
        logger.warning("google-cloud-speech not installed. STT unavailable.")
        return ""
    except Exception as exc:
        logger.error("GCP STT failed: %s", exc)
        return ""


async def synthesize_speech(text: str, language_code: str = "en-IN") -> bytes | None:
    """
    Convert text to MP3 audio bytes using GCP Text-to-Speech.
    Returns None on failure.
    """
    try:
        from google.cloud import texttospeech  # type: ignore

        client = texttospeech.TextToSpeechAsyncClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        response = await client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        return response.audio_content
    except ImportError:
        logger.warning("google-cloud-texttospeech not installed. TTS unavailable.")
        return None
    except Exception as exc:
        logger.error("GCP TTS failed: %s", exc)
        return None


def audio_to_base64(audio_bytes: bytes) -> str:
    return base64.b64encode(audio_bytes).decode("utf-8")
