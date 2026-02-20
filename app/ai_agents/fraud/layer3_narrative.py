"""
Layer 3 — LLM Narrative Analysis
Uses Gemini (via LangChain) to analyse the claim description + extracted document text for
inconsistencies, pressure language, or implausible medical jargon.
Degrades gracefully if LLM is unavailable (returns score=0.0).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_PRESSURE_PHRASES = [
    "urgent", "immediate payment", "or i will sue", "lawyer will contact",
    "final warning", "must pay today", "threatening",
]
_IMPLAUSIBLE_COMBOS = [
    ("dental", "motor accident"),
    ("maternity", "70 year"),
    ("pediatric", "adult only policy"),
]


def run(context: dict[str, Any], llm_enabled: bool = False) -> dict[str, Any]:
    flags: list[str] = []
    score = 0.0
    method = "rule_based"

    description = (context.get("description") or "").lower()
    extracted_text = (context.get("extracted_text") or "").lower()
    combined = f"{description} {extracted_text}"

    # Rule-based fallback (always runs)
    for phrase in _PRESSURE_PHRASES:
        if phrase in combined:
            flags.append(f"PRESSURE_PHRASE:{phrase!r}")
            score = max(score, 0.55)

    for term_a, term_b in _IMPLAUSIBLE_COMBOS:
        if term_a in combined and term_b in combined:
            flags.append(f"IMPLAUSIBLE_COMBO:{term_a}+{term_b}")
            score = max(score, 0.65)

    # LLM analysis (Gemini)
    # We ignore llm_enabled flag here to force Gemini usage if key is present,
    # or we respect it if user explicitly disables AI in config.
    # User wants AI agent here.
    if llm_enabled and not flags:
        try:
            score, llm_flags, method = _gemini_analysis(context)
            flags.extend(llm_flags)
        except Exception as exc:
            logger.warning("Gemini narrative analysis failed, using rule-based: %s", exc)

    return {
        "score": min(score, 1.0),
        "flags": flags,
        "layer": "narrative",
        "method": method,
        "ai_degraded": method != "gemini_llm",
    }


def _gemini_analysis(context: dict[str, Any]) -> tuple[float, list[str], str]:
    """Call Gemini for narrative analysis. Returns (score, flags, method)."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.prompts import PromptTemplate
        from app.config import settings
        import json

        if not settings.GCP_API_KEY:
            return 0.0, [], "skipped_no_key"

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GCP_API_KEY,
            temperature=0.1,
        )

        prompt = PromptTemplate.from_template(
            "Analyze this insurance claim for fraud indicators. "
            "Compare the claim description with the extracted document text.\n"
            "Claim Description: {description}\n"
            "Document Text: {extracted_text}\n\n"
            "Return valid JSON ONLY: {{\"score\": 0.0-1.0, \"flags\": [\"FLAG_NAME\"], \"reason\": \"explanation\"}}.\n"
            "Score 0.0 = Clean, 1.0 = Suspicious."
        )

        chain = prompt | llm
        
        # Trucate text to avoid token limits (though Gemini has 1M context)
        # Safe limit 30k chars
        d_text = str(context.get("extracted_text", ""))[:30000]
        
        response = chain.invoke({
            "description": context.get("description", ""),
            "extracted_text": d_text,
        })

        content = response.content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)

        return float(parsed.get("score", 0.0)), parsed.get("flags", []), "gemini_llm"

    except Exception as exc:
        raise RuntimeError(f"Gemini failed: {exc}") from exc
