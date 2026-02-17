"""
Speech Transcriber
STT integration. Backend failures are caught and re-raised as clear ValueError,
never as RuntimeError that callers don't handle.
"""
import io
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Optional, Union

logger = logging.getLogger(__name__)

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

try:
    import whisper as _whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


@dataclass
class TranscriptionResult:
    text: str
    confidence: Optional[float]
    language: str
    backend_used: str
    duration_seconds: Optional[float]


class SpeechTranscriber:
    """
    Transcribes audio to text.
    Raises ValueError (not RuntimeError) when no backend is available —
    callers must catch ValueError.
    """

    def __init__(self, backend: str = "auto", whisper_model: str = "base"):
        self.backend = self._select(backend)
        self.whisper_model_name = whisper_model
        self._whisper_model = None
        logger.info(f"SpeechTranscriber backend={self.backend}")

    def is_available(self) -> bool:
        return self.backend != "none"

    def transcribe(
        self,
        audio_input: Union[bytes, str],
        audio_format: str = "wav",
        language: str = "en-IN",
    ) -> TranscriptionResult:
        if not self.is_available():
            raise ValueError(
                "No STT backend available. "
                "Install 'SpeechRecognition' or 'openai-whisper'."
            )
        if self.backend == "whisper":
            return self._whisper(audio_input, language)
        return self._google(audio_input, language)

    # ── Whisper ──────────────────────────────────────────────────────────────

    def _whisper(self, audio_input: Union[bytes, str], language: str) -> TranscriptionResult:
        if not WHISPER_AVAILABLE:
            raise ValueError("openai-whisper not installed")
        if self._whisper_model is None:
            logger.info(f"Loading Whisper model '{self.whisper_model_name}'…")
            self._whisper_model = _whisper.load_model(self.whisper_model_name)

        if isinstance(audio_input, bytes):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_input)
                tmp = f.name
            try:
                result = self._whisper_model.transcribe(tmp, language="en", fp16=False)
            finally:
                os.unlink(tmp)
        else:
            result = self._whisper_model.transcribe(audio_input, language="en", fp16=False)

        text = result.get("text", "").strip()
        segs = result.get("segments", [])
        return TranscriptionResult(
            text=text,
            confidence=None,
            language=language,
            backend_used="whisper",
            duration_seconds=segs[-1]["end"] if segs else None,
        )

    # ── Google ───────────────────────────────────────────────────────────────

    def _google(self, audio_input: Union[bytes, str], language: str) -> TranscriptionResult:
        if not SR_AVAILABLE:
            raise ValueError("SpeechRecognition not installed")
        rec = sr.Recognizer()
        src = io.BytesIO(audio_input) if isinstance(audio_input, bytes) else open(audio_input, "rb")
        try:
            with sr.AudioFile(src) as source:
                rec.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = rec.record(source)
            text = rec.recognize_google(audio_data, language=language)
            return TranscriptionResult(
                text=text, confidence=None, language=language,
                backend_used="google", duration_seconds=None,
            )
        except sr.UnknownValueError:
            raise ValueError("Audio could not be understood")
        except sr.RequestError as e:
            raise ValueError(f"Google STT API error: {e}")
        finally:
            if not isinstance(audio_input, bytes):
                src.close()

    # ── Backend selection ─────────────────────────────────────────────────────

    def _select(self, backend: str) -> str:
        if backend != "auto":
            return backend
        if WHISPER_AVAILABLE:
            return "whisper"
        if SR_AVAILABLE:
            return "google"
        return "none"