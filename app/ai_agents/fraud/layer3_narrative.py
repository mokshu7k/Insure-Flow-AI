"""
Layer 3 – Narrative / AI Explanation Generator
Routes through privacy.py before any processing.

Engine modes
------------
Local (default, ENABLE_EXTERNAL_AI=False):
    Pure rule-based narrative built from flag descriptions.
    Zero network calls, deterministic, always available.

External AI (ENABLE_EXTERNAL_AI=True):
    Calls a self-hosted Ollama LLM instance (no data egress, DPDP-safe).
    Sends a structured JSON prompt containing only sanitized/anonymized
    claim signals — never raw PII.
    Enforces a hard wall-clock timeout (AI_TIMEOUT_SECONDS) via a
    ThreadPoolExecutor so the API thread is never blocked indefinitely.
    Falls back to local narrative on any failure.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from functools import lru_cache
from typing import Any, Dict, List

from app.ai_agents.fraud import config as cfg
from app.ai_agents.fraud import privacy
from app.ai_agents.fraud.schemas import NarrativeResult

logger = logging.getLogger(__name__)

# Single reusable executor — avoids spawning a thread per request
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fraud_ai")

# Sorted risk boundaries: highest threshold first for correct classification
_SORTED_BOUNDARIES: list[tuple[str, float]] = sorted(
    cfg.RISK_LEVEL_BOUNDARIES.items(), key=lambda kv: kv[1], reverse=True
)


# ---------------------------------------------------------------------------
# Risk-level classifier
# ---------------------------------------------------------------------------
def _classify_risk(score: float) -> str:
    """
    Return the highest matching risk level for *score*.

    Uses a pre-sorted list so classification is correct regardless of
    dict insertion order (fixes a subtle ordering bug in the original).
    """
    for level, boundary in _SORTED_BOUNDARIES:
        if score >= boundary:
            return level
    return "MINIMAL"


# ---------------------------------------------------------------------------
# Flag humaniser
# ---------------------------------------------------------------------------
_FLAG_DESCRIPTIONS: Dict[str, str] = {
    "AMOUNT_EXCEEDS_THRESHOLD":      "Claim amount exceeds typical threshold for this claim type",
    "SUSPICIOUSLY_ROUND_AMOUNT":     "Claim amount is a suspiciously round number",
    "INVALID_POLICY_FORMAT":         "Policy number format appears invalid",
    "AMOUNT_STATISTICAL_OUTLIER":    "Claim amount is a statistical outlier (>2.5 standard deviations)",
    "HIGH_RISK_PROVIDER_PATTERN":    "Provider has exhibited high-risk patterns in historical data",
    "TEMPORAL_CLUSTERING_DETECTED":  "Multiple claims detected in short time window",
    "UNUSUALLY_HIGH_CLAIM_FREQUENCY":"User has unusually high claim frequency",
    "CLAIM_AFTER_LONG_DORMANCY":     "First claim after extended period of policy inactivity",
    "CLAIM_NEAR_POLICY_EXPIRY":      "Claim submitted close to policy expiration date",
    "PREVIOUS_FRAUD_FLAGS_ON_RECORD":"User has previous fraud flags in historical records",
}


@lru_cache(maxsize=256)
def _humanize_flag(flag: str) -> str:
    """Cached flag → human description. LRU avoids repeated dict lookups per assessment."""
    return _FLAG_DESCRIPTIONS.get(flag, flag.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Recommendation text
# ---------------------------------------------------------------------------
def _recommendation(fraud_score: float) -> str:
    if fraud_score >= cfg.RISK_LEVEL_BOUNDARIES["HIGH"]:
        return (
            "This claim requires MANUAL REVIEW by an insurance adjuster "
            "before approval due to elevated fraud risk indicators."
        )
    if fraud_score >= cfg.RISK_LEVEL_BOUNDARIES["MODERATE"]:
        return "Consider additional verification steps before proceeding with approval."
    return "Fraud risk is within acceptable parameters. Standard processing may proceed."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def evaluate(
    claim_context: Dict[str, Any],
    deterministic_signals: List[str],
    statistical_anomalies: List[str],
    behavioral_flags: List[str],
    preliminary_score: float,
    privacy_mode: str | None = None,
) -> NarrativeResult:
    """
    Generate a structured fraud narrative.

    1. Sanitises input through ``privacy.py``.
    2. Attempts Ollama LLM call if ENABLE_EXTERNAL_AI=True (with timeout).
    3. Falls back to local rule-based narrative on any failure.

    Args:
        claim_context:         Raw claim data (PII will be sanitized before use).
        deterministic_signals: Flags from Layer 1.
        statistical_anomalies: Flags from Layer 2.
        behavioral_flags:      Behavioural subset of Layer 2 anomalies.
        preliminary_score:     Weighted score *before* narrative contribution.
        privacy_mode:          Override privacy mode (default from config).

    Returns:
        NarrativeResult with score in [0.0, 1.0] and structured reasoning.
    """
    ai_degraded_mode = False

    # Privacy gate — strips/masks PII before anything else touches the data
    sanitized_context = privacy.sanitize(claim_context, mode=privacy_mode)

    # Deduplicate flags (behavioral_flags is a subset of statistical_anomalies;
    # merging early avoids double-counting in signal density calculation)
    all_unique_flags: list[str] = list(dict.fromkeys(
        deterministic_signals + statistical_anomalies + behavioral_flags
    ))

    if cfg.ENABLE_EXTERNAL_AI:
        try:
            future = _EXECUTOR.submit(
                _call_external_ai,
                sanitized_context,
                deterministic_signals,
                statistical_anomalies,
                behavioral_flags,
                preliminary_score,
            )
            result = future.result(timeout=cfg.AI_TIMEOUT_SECONDS)
            return result
        except FuturesTimeoutError:
            logger.warning(
                "External AI timed out after %.1fs – falling back to local narrative.",
                cfg.AI_TIMEOUT_SECONDS,
            )
            ai_degraded_mode = True
        except Exception as exc:
            logger.warning("External AI call failed (%s) – falling back to local narrative.", exc)
            ai_degraded_mode = True

    return _build_local_narrative(
        sanitized_context,
        deterministic_signals,
        statistical_anomalies,
        behavioral_flags,
        all_unique_flags,
        preliminary_score,
        ai_degraded_mode=ai_degraded_mode,
    )


# ---------------------------------------------------------------------------
# Local narrative builder
# ---------------------------------------------------------------------------
def _build_local_narrative(
    sanitized_context: Dict[str, Any],
    deterministic_signals: List[str],
    statistical_anomalies: List[str],
    behavioral_flags: List[str],
    all_unique_flags: List[str],
    preliminary_score: float,
    *,
    ai_degraded_mode: bool = False,
) -> NarrativeResult:
    """Build a fully structured narrative without any external calls."""
    risk_level = _classify_risk(preliminary_score)

    # Build signal explanations — deduplicated via all_unique_flags
    signals_explained: Dict[str, str] = {
        flag: _humanize_flag(flag) for flag in all_unique_flags
    }

    structured_reasoning: Dict[str, object] = {
        "risk_level": risk_level,
        "summary": (
            f"Fraud risk assessment: {risk_level} "
            f"(score: {preliminary_score:.2f}). "
            f"{len(signals_explained)} unique signal(s) identified."
        ),
        "signals_explained": signals_explained,
        "recommendation": _recommendation(preliminary_score),
        "source": "local",
    }

    # Narrative score: based on unique signal count only (no double-counting)
    # Cap at 0.5 — narrative layer is a supporting signal, not the primary driver
    local_score = min(0.5, len(all_unique_flags) * 0.08)

    return NarrativeResult(
        score=local_score,
        structured_reasoning=structured_reasoning,
        ai_degraded_mode=ai_degraded_mode,
    )


# ---------------------------------------------------------------------------
# External AI — Ollama (self-hosted, no data egress)
# ---------------------------------------------------------------------------
def _build_ollama_prompt(
    sanitized_context: Dict[str, Any],
    deterministic_signals: List[str],
    statistical_anomalies: List[str],
    behavioral_flags: List[str],
    preliminary_score: float,
) -> str:
    """
    Build a structured JSON prompt for the Ollama LLM.

    The prompt instructs the model to return ONLY a JSON object — no prose —
    so the response can be parsed deterministically.
    """
    signal_descriptions = {flag: _humanize_flag(flag) for flag in dict.fromkeys(
        deterministic_signals + statistical_anomalies + behavioral_flags
    )}

    payload = {
        "claim_type": sanitized_context.get("claim_type", "UNKNOWN"),
        "amount_band": sanitized_context.get("claim_amount", "UNKNOWN"),
        "policy_status": sanitized_context.get("policy_status", "UNKNOWN"),
        "preliminary_fraud_score": round(preliminary_score, 4),
        "deterministic_signals": deterministic_signals,
        "statistical_anomalies": statistical_anomalies,
        "behavioral_flags": behavioral_flags,
        "signal_descriptions": signal_descriptions,
    }

    return (
        "You are an insurance fraud analysis engine. "
        "Analyse the following claim signals and return ONLY a JSON object with these exact keys:\n"
        "  risk_level: one of VERY_HIGH / HIGH / MODERATE / LOW / MINIMAL\n"
        "  score_adjustment: a float between -0.10 and 0.10 (positive = higher fraud risk)\n"
        "  summary: one sentence summarising fraud risk\n"
        "  key_concerns: list of up to 3 strings identifying the most important signals\n"
        "  recommendation: one sentence action recommendation\n\n"
        "Do NOT include any text outside the JSON object.\n\n"
        f"Claim data:\n{json.dumps(payload, indent=2)}"
    )


def _call_external_ai(
    sanitized_context: Dict[str, Any],
    deterministic_signals: List[str],
    statistical_anomalies: List[str],
    behavioral_flags: List[str],
    preliminary_score: float,
) -> NarrativeResult:
    """
    Call a self-hosted Ollama LLM for narrative generation.

    - Sends only sanitized/anonymized claim signals (no PII ever leaves the service).
    - Enforces AI_TIMEOUT_SECONDS via the caller (ThreadPoolExecutor.result(timeout=...)).
    - Parses the structured JSON response from the model.
    - Falls back to local narrative if the model returns malformed JSON.

    Ollama endpoint: POST {EXTERNAL_AI_BASE_URL}/api/generate
    """
    import requests  # soft import — only needed when ENABLE_EXTERNAL_AI=True

    prompt = _build_ollama_prompt(
        sanitized_context,
        deterministic_signals,
        statistical_anomalies,
        behavioral_flags,
        preliminary_score,
    )

    url = f"{cfg.EXTERNAL_AI_BASE_URL}/api/generate"
    payload = {
        "model": cfg.EXTERNAL_AI_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": cfg.EXTERNAL_AI_MAX_TOKENS,
            "temperature": 0.1,   # low temperature = deterministic, factual responses
            "top_p": 0.9,
        },
    }

    logger.debug("Calling Ollama at %s with model=%s", url, cfg.EXTERNAL_AI_MODEL)
    response = requests.post(url, json=payload, timeout=cfg.AI_TIMEOUT_SECONDS)
    response.raise_for_status()

    raw_text: str = response.json().get("response", "").strip()
    logger.debug("Ollama raw response: %s", raw_text[:200])

    # Parse JSON response from the model
    try:
        # Strip markdown code fences if the model wraps output in ```json ... ```
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        ai_data: Dict[str, Any] = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Ollama returned non-JSON response (%s) — using local fallback.", exc)
        raise ValueError(f"Non-JSON response from Ollama: {exc}") from exc

    # Validate and clamp score_adjustment
    raw_adjustment = float(ai_data.get("score_adjustment", 0.0))
    score_adjustment = max(-0.10, min(0.10, raw_adjustment))

    # Final narrative score: preliminary + model's adjustment, clamped to [0, 1]
    final_score = max(0.0, min(1.0, preliminary_score + score_adjustment))

    # Build a structured_reasoning dict consistent with local narrative format
    risk_level = ai_data.get("risk_level") or _classify_risk(final_score)
    structured_reasoning: Dict[str, object] = {
        "risk_level": risk_level,
        "summary": ai_data.get("summary", ""),
        "key_concerns": ai_data.get("key_concerns", []),
        "signals_explained": {flag: _humanize_flag(flag) for flag in dict.fromkeys(
            deterministic_signals + statistical_anomalies + behavioral_flags
        )},
        "recommendation": ai_data.get("recommendation", _recommendation(final_score)),
        "source": f"ollama/{cfg.EXTERNAL_AI_MODEL}",
        "score_adjustment": score_adjustment,
    }

    logger.info(
        "Ollama narrative complete: risk=%s score_adj=%.3f model=%s",
        risk_level, score_adjustment, cfg.EXTERNAL_AI_MODEL,
    )

    return NarrativeResult(
        score=final_score,
        structured_reasoning=structured_reasoning,
        ai_degraded_mode=False,
    )
