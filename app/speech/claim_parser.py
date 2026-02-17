"""
Speech Claim Parser
Transcribe audio → extract structured claim fields → return draft.
ALWAYS requires human confirmation before any DB write.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Optional, Union

from app.speech.transcriber import SpeechTranscriber, TranscriptionResult

logger = logging.getLogger(__name__)


@dataclass
class SpeechClaimDraft:
    claim_type: Optional[str] = None
    claim_amount: Optional[float] = None
    policy_number: Optional[str] = None
    incident_description: str = ""
    incident_date: Optional[str] = None
    hospital_name: Optional[str] = None
    vehicle_number: Optional[str] = None
    transcription_text: str = ""
    confidence: float = 0.0
    requires_confirmation: bool = True   # ALWAYS True
    missing_fields: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class SpeechClaimParser:
    """
    Extracts claim fields from voice input.
    Never submits automatically — always returns a draft for UI confirmation.
    """

    CLAIM_TYPE_KEYWORDS = {
        "HEALTH": [
            "hospital", "hospitalization", "admitted", "surgery", "operation",
            "treatment", "doctor", "medicine", "medical", "emergency",
            "icu", "ward", "diagnosis", "prescription", "opd", "ipd",
        ],
        "MOTOR": [
            "accident", "car", "vehicle", "bike", "truck", "collision",
            "damage", "repair", "workshop", "garage", "scratch", "dent",
            "fir", "police", "motor", "automobile", "crash",
        ],
        "REIMBURSEMENT": [
            "reimbursement", "reimburse", "paid", "expense", "bill",
            "receipt", "out of pocket", "already paid",
        ],
    }

    _AMOUNT_PATTERNS = [
        re.compile(r"(?:rs\.?|inr|rupees?|₹)\s*([\d,]+(?:\.\d{1,2})?)", re.I),
        re.compile(r"([\d,]+(?:\.\d{1,2})?)\s*(?:rs\.?|inr|rupees?|₹)", re.I),
        re.compile(r"\b(\d+)\s*lakh\b", re.I),
        re.compile(r"\b(\d+)\s*thousand\b", re.I),
    ]
    _POLICY_RE = re.compile(
        r"\bpol(?:icy)?\s*(?:no\.?|number|#)?\s*[:\-]?\s*([A-Za-z0-9\-]{6,20})\b", re.I
    )
    _DATE_RE = re.compile(
        r"\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b|"
        r"\b(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\.?\s+\d{2,4})\b",
        re.I,
    )
    _VEHICLE_RE = re.compile(r"\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,2}\s*\d{4})\b", re.I)

    def __init__(self, backend: str = "auto"):
        self.transcriber = SpeechTranscriber(backend=backend)

    # ── Public API ────────────────────────────────────────────────────────────

    def parse_audio(
        self,
        audio_bytes: bytes,
        audio_format: str = "wav",
        language: str = "en-IN",
    ) -> SpeechClaimDraft:
        try:
            result: TranscriptionResult = self.transcriber.transcribe(
                audio_bytes, audio_format, language
            )
            return self.parse_text(result.text, confidence=0.70)
        except ValueError as exc:
            # ValueError from transcriber (no backend, bad audio) → empty draft
            draft = SpeechClaimDraft()
            draft.warnings.append(str(exc))
            draft.missing_fields = ["claim_type", "claim_amount", "policy_number"]
            return draft

    def parse_text(self, text: str, confidence: float = 1.0) -> SpeechClaimDraft:
        draft = SpeechClaimDraft(
            transcription_text=text,
            confidence=confidence,
            requires_confirmation=True,
        )
        if not text.strip():
            draft.warnings.append("Empty transcription")
            draft.missing_fields = ["claim_type", "claim_amount", "policy_number"]
            return draft

        draft.claim_type = self._detect_type(text)
        draft.claim_amount = self._extract_amount(text)
        draft.policy_number = self._extract_policy(text)
        draft.incident_date = self._extract_date(text)
        draft.vehicle_number = self._extract_vehicle(text)
        draft.incident_description = text.strip()[:1000]
        draft.missing_fields = self._missing(draft)

        if draft.claim_amount and draft.claim_amount > 500_000:
            draft.warnings.append("Large amount detected — verify before confirming")
        if confidence < 0.6:
            draft.warnings.append("Low transcription confidence — verify all fields")

        return draft

    # ── Field extractors ──────────────────────────────────────────────────────

    def _detect_type(self, text: str) -> Optional[str]:
        low = text.lower()
        scores = {
            t: sum(1 for kw in kws if kw in low)
            for t, kws in self.CLAIM_TYPE_KEYWORDS.items()
        }
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else None

    def _extract_amount(self, text: str) -> Optional[float]:
        low = text.lower()
        for pat in self._AMOUNT_PATTERNS:
            m = pat.search(low)
            if m:
                raw = m.group(1).replace(",", "")
                try:
                    amount = float(raw)
                    if "lakh" in low or "lac" in low:
                        amount *= 100_000
                    elif "thousand" in low:
                        amount *= 1_000
                    return amount
                except ValueError:
                    continue
        return None

    def _extract_policy(self, text: str) -> Optional[str]:
        m = self._POLICY_RE.search(text)
        return m.group(1).strip() if m else None

    def _extract_date(self, text: str) -> Optional[str]:
        m = self._DATE_RE.search(text)
        return (m.group(1) or m.group(2)).strip() if m else None

    def _extract_vehicle(self, text: str) -> Optional[str]:
        m = self._VEHICLE_RE.search(text)
        return m.group(1).strip() if m else None

    def _missing(self, draft: SpeechClaimDraft) -> list:
        out = []
        if not draft.claim_type:
            out.append("claim_type")
        if not draft.claim_amount:
            out.append("claim_amount")
        if not draft.policy_number:
            out.append("policy_number")
        return out