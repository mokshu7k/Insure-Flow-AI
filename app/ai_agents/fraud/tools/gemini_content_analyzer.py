"""
Gemini Content Analyzer — LLM-powered document fraud analysis.

Uses Gemini's medical / financial knowledge to detect:
  • Diagnosis-treatment inconsistencies
  • Drug-diagnosis mismatches
  • Unreasonable pricing (Indian healthcare context)
  • Implausible treatment durations / phantom charges
  • Risk synthesis & explanation for the final aggregator

Two public async functions:
  1. ``analyze_document_content()`` — per-document content fraud analysis
  2. ``generate_risk_synthesis()``   — final cross-node explanation
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ── Shared LLM helpers ────────────────────────────────────────────────────────

def _get_llm(temperature: float = 0.1):
    """Create a Gemini LLM instance (reusable across callers)."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    from app.config import settings

    if not settings.GCP_API_KEY:
        raise ValueError("No GCP_API_KEY configured")

    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GCP_API_KEY,
        temperature=temperature,
        max_output_tokens=4096,
    )


def _parse_json_response(content: str) -> dict | None:
    """Robustly extract JSON from an LLM response."""
    content = content.strip()

    # Strip markdown code fences
    fence = re.search(r"```(?:json)?\s*\n?(.*?)```", content, re.DOTALL)
    if fence:
        content = fence.group(1).strip()
    else:
        brace_start = content.find("{")
        brace_end = content.rfind("}")
        if brace_start != -1 and brace_end != -1:
            content = content[brace_start : brace_end + 1]

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


# ── Document-type-specific checklists ──────────────────────────────────────────

_HOSPITAL_BILL_CHECKLIST = """
1. Are the procedures/treatments consistent with the stated diagnosis?
2. Are room charges (ICU/general ward/deluxe) proportionate to the condition?
3. Are consumable costs reasonable or suspiciously inflated (>3× typical)?
4. Are there phantom charges (items unrelated to the treatment)?
5. Are there duplicate charges (same service billed twice)?
6. Is the duration of stay appropriate for the diagnosis/procedure?
7. Are investigation/test charges reasonable for the condition?
8. Is the total amount plausible for the diagnosis in Indian healthcare?
"""

_DISCHARGE_SUMMARY_CHECKLIST = """
1. Does the stated diagnosis match the reported treatment/procedures?
2. Is the treatment appropriate and not excessive (overkill) for the condition?
3. Is the hospital stay duration reasonable for the diagnosis?
4. Are there inconsistencies in the clinical timeline (admission > discharge)?
5. Does the condition at discharge make medical sense given the treatment?
6. Are the mentioned medications consistent with the diagnosis?
"""

_PRESCRIPTION_CHECKLIST = """
1. Are the prescribed drugs appropriate for the stated diagnosis?
2. Are there expensive specialty drugs (oncology, biologics) that seem unnecessary?
3. Are dosages within standard ranges?
4. Are there obvious drug interactions that a real doctor would avoid?
5. Is the quantity/duration of prescription suspicious (e.g. 90-day supply for acute)?
"""

_LAB_REPORT_CHECKLIST = """
1. Are the tests relevant to the stated diagnosis or condition?
2. Are the test values within physiologically possible ranges?
3. Are there unnecessary or excessive tests ordered?
4. Do the results correlate with the stated diagnosis?
"""

_GENERAL_CHECKLIST = """
1. Is the content internally consistent?
2. Are there obvious irregularities in the document data?
3. Do amounts and quantities make general sense?
"""

_CHECKLISTS = {
    "HOSPITAL_BILL":     _HOSPITAL_BILL_CHECKLIST,
    "DISCHARGE_SUMMARY": _DISCHARGE_SUMMARY_CHECKLIST,
    "PRESCRIPTION":      _PRESCRIPTION_CHECKLIST,
    "LAB_REPORT":        _LAB_REPORT_CHECKLIST,
    "PHARMACY_BILL":     _PRESCRIPTION_CHECKLIST,   # similar checks
}


# ── Document content analysis ─────────────────────────────────────────────────

async def analyze_document_content(
    document_type: str,
    extracted_data: dict[str, Any],
    arithmetic_results: dict[str, Any] | None = None,
    gst_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Use Gemini to analyse a single document's content for fraud signals.

    Returns
    -------
    dict with keys:
        signals: list[dict]   — each {signal, severity, category}
        medical_plausibility: str   — PLAUSIBLE | QUESTIONABLE | IMPLAUSIBLE
        risk_score: int  0-100
        summary: str
    """
    try:
        llm = _get_llm()
    except (ValueError, ImportError) as exc:
        logger.warning("Gemini unavailable for content analysis: %s", exc)
        return {
            "signals": [],
            "medical_plausibility": "UNKNOWN",
            "risk_score": 0,
            "summary": f"Skipped — {exc}",
            "skipped": True,
        }

    checklist = _CHECKLISTS.get(document_type, _GENERAL_CHECKLIST)

    # Pre-computed deterministic context
    deterministic_ctx = ""
    if arithmetic_results:
        arith_flags = arithmetic_results.get("flags", [])
        if arith_flags:
            deterministic_ctx += f"\nArithmetic validation flags: {arith_flags}"
    if gst_results:
        gst_flags = gst_results.get("flags", [])
        if gst_flags:
            deterministic_ctx += f"\nGST validation flags: {gst_flags}"

    # Sanitise extracted data (remove binary, large fields)
    clean = {
        k: v for k, v in extracted_data.items()
        if not isinstance(v, (bytes, bytearray)) and k != "raw_text"
    }

    prompt = (
        f"You are an expert Indian insurance claim fraud investigator.\n"
        f"Analyse the following {document_type} for potential fraud indicators.\n\n"
        f"DOCUMENT DATA:\n{json.dumps(clean, indent=2, default=str)[:6000]}\n\n"
        f"{('DETERMINISTIC CHECK RESULTS:' + deterministic_ctx) if deterministic_ctx else ''}\n\n"
        f"ANALYSIS CHECKLIST for {document_type}:\n{checklist}\n\n"
        "IMPORTANT RULES:\n"
        "- Only flag genuinely suspicious items, NOT normal variations.\n"
        "- Base your analysis on Indian healthcare pricing and practices.\n"
        "- Consider that amounts are in Indian Rupees (₹ / INR).\n"
        "- If data is insufficient to judge, do NOT fabricate signals.\n"
        "- Be conservative — if something seems normal, don't flag it.\n\n"
        "Return ONLY valid JSON (no markdown, no explanation outside JSON):\n"
        '{\n'
        '  "signals": [\n'
        '    {"signal": "description", "severity": "LOW|MEDIUM|HIGH|CRITICAL", '
        '"category": "PRICING|MEDICAL|TEMPORAL|DOCUMENTATION"}\n'
        '  ],\n'
        '  "medical_plausibility": "PLAUSIBLE|QUESTIONABLE|IMPLAUSIBLE",\n'
        '  "risk_score": 0,\n'
        '  "summary": "one-line explanation"\n'
        '}\n\n'
        "If the document appears clean and consistent return an empty signals list, "
        'risk_score 0, and medical_plausibility "PLAUSIBLE".'
    )

    try:
        response = await llm.ainvoke(prompt)
        result = _parse_json_response(response.content)

        if not result:
            logger.warning("Failed to parse Gemini content-analysis response")
            return {
                "signals": [],
                "medical_plausibility": "UNKNOWN",
                "risk_score": 0,
                "summary": "Failed to parse Gemini response",
                "parse_error": True,
            }

        # Sanitise / clamp
        result["risk_score"] = max(0, min(100, int(result.get("risk_score", 0))))
        if not isinstance(result.get("signals"), list):
            result["signals"] = []

        return result

    except Exception as exc:
        logger.error("Gemini content analysis failed: %s", exc)
        return {
            "signals": [],
            "medical_plausibility": "UNKNOWN",
            "risk_score": 0,
            "summary": f"Gemini error — {exc}",
            "error": True,
        }


# ── Risk synthesis (called by aggregator) ─────────────────────────────────────

async def generate_fraud_score_and_synthesis(
    node_results: dict[str, Any],
    all_flags: list[str],
) -> dict[str, Any]:
    """Gemini-powered FINAL scoring + risk synthesis for the aggregator.

    Instead of a static weighted formula this function sends every node's
    key findings to Gemini and asks it to:
      1. Determine a final fraud-risk score (0-1).
      2. Assign a risk level.
      3. Produce a human-readable explanation.
      4. Identify the critical signals.
      5. Recommend manual review or not.

    Falls back to a deterministic heuristic if Gemini is unreachable.

    Returns
    -------
    dict with:
        final_score: float            — 0 to 1
        risk_level: str               — MINIMAL | LOW | MEDIUM | HIGH | VERY_HIGH
        risk_explanation: str
        critical_signals: list[str]
        manual_review_recommended: bool
        confidence: str               — HIGH | MEDIUM | LOW
    """
    # ── Build compact per-node digest for the prompt ──────────────────────
    node_digests: dict[str, Any] = {}
    for name, data in node_results.items():
        if not isinstance(data, dict):
            continue
        flags = data.get("flags", [])
        checks = data.get("checks", data.get("details", {}))
        node_digests[name] = {
            "score_0_to_100": data.get("score", 0),
            "flag_count": len(flags),
            "flags": flags[:8],          # top 8 flags per node
            "key_checks": _compact_checks(checks),
            "skipped": data.get("skipped", False),
            "error": data.get("error"),
        }

    # ── Deterministic fallback (used if LLM fails) ───────────────────────
    def _deterministic_fallback() -> dict[str, Any]:
        """Simple max-of-nodes heuristic when Gemini is unavailable."""
        scores = [
            d.get("score", 0) / 100.0
            for d in node_results.values()
            if isinstance(d, dict) and not d.get("skipped")
        ]
        if not scores:
            return {
                "final_score": 0.0,
                "risk_level": "MINIMAL",
                "risk_explanation": "No node produced a score.",
                "critical_signals": [],
                "manual_review_recommended": False,
                "confidence": "LOW",
            }
        # Use a blend: 60 % max-score + 40 % average
        avg = sum(scores) / len(scores)
        mx  = max(scores)
        blended = round(0.6 * mx + 0.4 * avg, 4)

        if blended >= 0.85:   rl = "VERY_HIGH"
        elif blended >= 0.70: rl = "HIGH"
        elif blended >= 0.50: rl = "MEDIUM"
        elif blended >= 0.30: rl = "LOW"
        else:                 rl = "MINIMAL"

        return {
            "final_score": blended,
            "risk_level": rl,
            "risk_explanation": (
                f"Deterministic fallback — blended score {blended:.4f} ({rl}). "
                f"{len(all_flags)} signal(s) across {len(node_results)} nodes."
            ),
            "critical_signals": all_flags[:5],
            "manual_review_recommended": blended >= 0.50,
            "confidence": "LOW",
        }

    # ── Try Gemini ────────────────────────────────────────────────────────
    try:
        llm = _get_llm(temperature=0.05)
    except (ValueError, ImportError):
        return _deterministic_fallback()

    prompt = (
        "You are an expert insurance fraud risk analyst.\n\n"
        "Below are the results of 6 specialised fraud-detection nodes that "
        "analysed an insurance claim document. Each node scores risk 0-100 "
        "and raises flags describing what was found.\n\n"
        "YOUR JOB:\n"
        "1. Look at every node's score, flags, and key checks.\n"
        "2. Decide a FINAL fraud-risk score on a 0-1 scale (0 = clean, 1 = certain fraud).\n"
        "   - A single critical finding (e.g. copy-move, duplicate hash, "
        "     document tampering) can push the score above 0.8 even if other "
        "     nodes are clean.\n"
        "   - Many low-severity flags should compound but not reach HIGH unless "
        "     there is corroborating evidence across nodes.\n"
        "   - Skipped or errored nodes should NEITHER help nor hurt the score.\n"
        "3. Assign a risk level: MINIMAL (<0.30), LOW (0.30-0.49), "
        "   MEDIUM (0.50-0.69), HIGH (0.70-0.84), VERY_HIGH (≥0.85).\n"
        "4. Write a 2-4 sentence explanation referencing key findings.\n"
        "5. List the 3-5 most critical signals.\n"
        "6. Recommend manual review (true / false).\n\n"
        "NODE RESULTS:\n"
        f"{json.dumps(node_digests, indent=2, default=str)}\n\n"
        f"ALL FLAGS ({len(all_flags)} total, showing top 30):\n"
        f"{json.dumps(all_flags[:30], indent=2)}\n\n"
        "Return ONLY valid JSON — no markdown fences, no explanation "
        "outside the JSON object:\n"
        "{\n"
        '  "final_score": 0.45,\n'
        '  "risk_level": "MEDIUM",\n'
        '  "risk_explanation": "...",\n'
        '  "critical_signals": ["signal1", "signal2"],\n'
        '  "manual_review_recommended": true,\n'
        '  "confidence": "HIGH"\n'
        "}\n"
    )

    try:
        response = await llm.ainvoke(prompt)
        result = _parse_json_response(response.content)

        if not result or "final_score" not in result:
            logger.warning("Gemini scoring response unparseable — using fallback")
            return _deterministic_fallback()

        # Sanitise / clamp
        score = float(result["final_score"])
        score = max(0.0, min(1.0, round(score, 4)))
        result["final_score"] = score

        # Ensure risk_level is valid
        valid_levels = {"MINIMAL", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"}
        if result.get("risk_level") not in valid_levels:
            if score >= 0.85:   result["risk_level"] = "VERY_HIGH"
            elif score >= 0.70: result["risk_level"] = "HIGH"
            elif score >= 0.50: result["risk_level"] = "MEDIUM"
            elif score >= 0.30: result["risk_level"] = "LOW"
            else:               result["risk_level"] = "MINIMAL"

        if not isinstance(result.get("critical_signals"), list):
            result["critical_signals"] = all_flags[:5]
        if not isinstance(result.get("risk_explanation"), str):
            result["risk_explanation"] = ""
        if not isinstance(result.get("manual_review_recommended"), bool):
            result["manual_review_recommended"] = score >= 0.50
        if result.get("confidence") not in ("HIGH", "MEDIUM", "LOW"):
            result["confidence"] = "MEDIUM"

        return result

    except Exception as exc:
        logger.error("Gemini fraud scoring failed: %s", exc)
        return _deterministic_fallback()


def _compact_checks(checks: Any) -> Any:
    """Shrink a nested checks dict to only the keys the LLM needs."""
    if not isinstance(checks, dict):
        return checks
    compact: dict[str, Any] = {}
    for k, v in checks.items():
        if isinstance(v, dict):
            # Keep only the most informative keys
            mini = {ck: cv for ck, cv in v.items()
                    if ck in ("passed", "skipped", "valid", "flag_count",
                              "match_rate", "difference_pct", "duplicate_pairs",
                              "clone_regions", "noise_consistent", "ela_mean",
                              "checksum_passed", "is_masked", "has_exif",
                              "software", "risk_score", "comparisons",
                              "not_found_count", "privacy_violations",
                              "hallucinated_fields", "hot_pixel_pct",
                              "hotspot_ratio", "ssim")}
            compact[k] = mini
        else:
            compact[k] = v
    return compact


# ── Legacy compatibility wrapper (kept for existing callers) ──────────────────

async def generate_risk_synthesis(
    node_results: dict[str, Any],
    all_flags: list[str],
    final_score: float,
    risk_level: str,
) -> dict[str, Any]:
    """Gemini-powered final risk explanation for the aggregator.

    Returns
    -------
    dict with:
        risk_explanation: str
        critical_signals: list[str]
        manual_review_recommended: bool
        confidence: str
    """
    # Fallback if Gemini is unavailable
    fallback = {
        "risk_explanation": (
            f"Automated fraud analysis score: {final_score:.4f} ({risk_level}). "
            f"{len(all_flags)} signal(s) detected."
        ),
        "critical_signals": all_flags[:5],
        "manual_review_recommended": final_score >= 0.50,
        "confidence": "LOW",
    }

    try:
        llm = _get_llm(temperature=0.05)
    except (ValueError, ImportError):
        fallback["skipped"] = True
        return fallback

    # Compact per-node summary
    node_summaries = {}
    for name, data in node_results.items():
        if isinstance(data, dict):
            node_summaries[name] = {
                "score": data.get("score", 0),
                "flag_count": len(data.get("flags", [])),
                "top_flags": data.get("flags", [])[:3],
            }

    prompt = (
        "You are an insurance fraud risk analyst. Synthesise the following "
        "fraud detection results into a clear, actionable assessment.\n\n"
        f"RESULTS:\n"
        f"- Final Score: {final_score:.4f} (0-1 scale)\n"
        f"- Risk Level: {risk_level}\n"
        f"- Total Signals: {len(all_flags)}\n\n"
        f"NODE BREAKDOWN:\n{json.dumps(node_summaries, indent=2, default=str)}\n\n"
        f"ALL SIGNALS (top 20):\n{json.dumps(all_flags[:20], indent=2)}\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "risk_explanation": "2-3 sentence explanation mentioning key findings",\n'
        '  "critical_signals": ["top 3-5 most important signals"],\n'
        '  "manual_review_recommended": true or false,\n'
        '  "confidence": "HIGH|MEDIUM|LOW"\n'
        "}"
    )

    try:
        response = await llm.ainvoke(prompt)
        result = _parse_json_response(response.content)
        if result:
            return result
        return fallback
    except Exception as exc:
        logger.error("Risk synthesis failed: %s", exc)
        return fallback
