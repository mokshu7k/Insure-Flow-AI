"""
Node 3: Document Intelligence — Redaction, Hallucination & ID Validation.

A multi-pronged deterministic check that catches:
  1. Redaction bypass   — Gemini "seeing through" masked IDs (privacy violation)
  2. Hallucinated digits — Gemini inventing digits not in the source (fraud)
  3. Semantic-to-Raw mismatch — Gemini "editing" names / fields (cross-pollination)
  4. PAN structural validation — position-based rules
  5. Aadhaar Verhoeff checksum — mathematical proof the number is valid

All checks are deterministic Python — no LLM calls.  Uses the raw_text
from Node 1 (PyMuPDF) as the "undeniable truth" ground.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.messages import AIMessage

from app.ai_agents.fraud.state import FraudAgentState

logger = logging.getLogger(__name__)

# ── Risk weights per sub-check ────────────────────────────────────────────────
RISK_WEIGHTS = {
    "redaction_privacy":    90,   # Model leaked masked data
    "redaction_hallucination": 70, # Model invented digits
    "raw_mismatch":         60,   # Key fields not in raw text
    "pan_invalid":          50,   # PAN fails structural rules
    "pan_not_individual":   30,   # PAN holder type wrong for personal claim
    "aadhaar_checksum":     80,   # Aadhaar Verhoeff fails → fake number
    "aadhaar_unmasked":     60,   # Full Aadhaar extracted (compliance risk)
}


def _calculate_intelligence_score(checks: dict[str, dict[str, Any]]) -> tuple[float, list[str]]:
    """Calculate document intelligence risk score (0–100)."""
    penalties: list[float] = []
    all_flags: list[str] = []

    # Redaction integrity
    redaction = checks.get("redaction_integrity", {})
    if not redaction.get("passed", True):
        for field in redaction.get("privacy_violations", []):
            penalties.append(RISK_WEIGHTS["redaction_privacy"])
            all_flags.append(f"REDACTION_PRIVACY: Gemini bypassed mask on '{field}'")
        for field in redaction.get("hallucinated_fields", []):
            penalties.append(RISK_WEIGHTS["redaction_hallucination"])
            all_flags.append(f"REDACTION_HALLUCINATION: Gemini invented digits for '{field}'")

    # Greedy string matcher
    matcher = checks.get("greedy_matcher", {})
    if not matcher.get("passed", True):
        not_found = matcher.get("not_found", [])
        match_rate = matcher.get("match_rate", 1.0)
        n_mismatches = len(not_found)
        # Penalty scales with number of mismatches
        penalty = min(RISK_WEIGHTS["raw_mismatch"] * n_mismatches, 100)
        penalties.append(penalty)
        for nf in not_found[:5]:
            all_flags.append(
                f"RAW_MISMATCH: '{nf['field']}'='{nf['gemini_value']}' not in raw PDF"
            )

    # PAN validation
    pan_check = checks.get("pan_validation", {})
    if pan_check and not pan_check.get("skipped"):
        if not pan_check.get("valid"):
            penalties.append(RISK_WEIGHTS["pan_invalid"])
            all_flags.extend(pan_check.get("flags", []))
        elif pan_check.get("flags"):  # valid format but wrong status code
            penalties.append(RISK_WEIGHTS["pan_not_individual"])
            all_flags.extend(pan_check.get("flags", []))

    # Aadhaar validation
    aadhaar_check = checks.get("aadhaar_validation", {})
    if aadhaar_check and not aadhaar_check.get("skipped"):
        if not aadhaar_check.get("is_masked", False):
            # Full Aadhaar was extracted — compliance risk even if valid
            all_flags.append("AADHAAR_FULL_EXTRACTED: full 12-digit Aadhaar in extraction (compliance risk)")
            penalties.append(RISK_WEIGHTS["aadhaar_unmasked"])

        if not aadhaar_check.get("valid", True) and not aadhaar_check.get("is_masked", True):
            penalties.append(RISK_WEIGHTS["aadhaar_checksum"])
            all_flags.extend(aadhaar_check.get("flags", []))

    if not penalties:
        return 0.0, all_flags

    max_penalty = max(penalties)
    others = sum(p for p in penalties if p != max_penalty)
    additional = min(25.0, others * 0.2)
    score = min(100.0, max_penalty + additional)

    return round(score, 1), all_flags


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  THE NODE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def document_intelligence_node(
    state: FraudAgentState,
    config: dict | None = None,
) -> dict[str, Any]:
    """LangGraph node — document intelligence analysis.

    Reads:
        state["raw_text"]            — from Node 1 (PyMuPDF)
        state["primary_extraction"]  — from Node 1 (Gemini JSON)
        state["document_type_code"]

    Writes:
        intelligence_checks, intelligence_risk_score, intelligence_flags,
        node_results (partial), messages
    """
    from app.ai_agents.fraud.tools.redaction_checker import (
        check_redaction_integrity,
        greedy_string_matcher,
    )
    from app.ai_agents.fraud.tools.id_validator import (
        validate_pan,
        validate_aadhaar,
    )

    claim_id = state.get("claim_id", "unknown")
    doc_type = state.get("document_type_code", "UNKNOWN")
    raw_text = state.get("raw_text") or ""
    extracted = state.get("primary_extraction") or state.get("existing_extracted_data") or {}

    logger.info(
        "Node 3 [Document Intelligence] starting — claim=%s, doc_type=%s, raw_text_len=%d",
        claim_id, doc_type, len(raw_text),
    )
    t_start = time.perf_counter()

    result: dict[str, Any] = {
        "intelligence_checks": {},
        "intelligence_risk_score": 0.0,
        "intelligence_flags": [],
    }

    has_text_layer = len(raw_text.strip()) > 20
    checks: dict[str, Any] = {}

    try:
        # ── Sub-check 1 & 2: Redaction Integrity ──────────────────────────────────
        if has_text_layer:
            logger.info("Step 1: Redaction integrity check…")
            checks["redaction_integrity"] = check_redaction_integrity(extracted, raw_text)
        else:
            checks["redaction_integrity"] = {
                "passed": True, "skipped": True,
                "skip_reason": "no_text_layer",
                "checks": [], "privacy_violations": [], "hallucinated_fields": [],
            }

        # ── Sub-check 3: Greedy String Matcher (Semantic-to-Raw) ──────────────────
        if has_text_layer:
            logger.info("Step 2: Greedy string matcher…")
            checks["greedy_matcher"] = greedy_string_matcher(extracted, raw_text)
        else:
            checks["greedy_matcher"] = {
                "passed": True, "skipped": True,
                "skip_reason": "no_text_layer",
                "total_checked": 0, "found_count": 0, "not_found": [], "match_rate": 1.0,
            }

        # ── Sub-check 4: PAN Validation ───────────────────────────────────────────
        pan_number = (
            extracted.get("pan_number")
            or (extracted.get("document_number") if doc_type == "PAN" else None)
        )
        if pan_number:
            logger.info("Step 3: PAN structural validation…")
            checks["pan_validation"] = validate_pan(pan_number, expect_individual=True)
        else:
            checks["pan_validation"] = {"skipped": True, "skip_reason": "no_pan_in_extraction"}

        # ── Sub-check 5: Aadhaar Verhoeff Validation ──────────────────────────────
        aadhaar_number = (
            extracted.get("aadhaar_number")
            or (extracted.get("document_number") if doc_type == "AADHAAR" else None)
        )
        if aadhaar_number:
            logger.info("Step 4: Aadhaar Verhoeff validation…")
            checks["aadhaar_validation"] = validate_aadhaar(aadhaar_number)
        else:
            checks["aadhaar_validation"] = {"skipped": True, "skip_reason": "no_aadhaar_in_extraction"}

        result["intelligence_checks"] = checks

        # Calculate composite score
        score, flags = _calculate_intelligence_score(checks)
        result["intelligence_risk_score"] = score
        result["intelligence_flags"] = flags

        elapsed = time.perf_counter() - t_start

        # Merge into node_results
        existing_nr = state.get("node_results") or {}
        existing_nr["document_intelligence"] = {
            "score": score,
            "flags": flags,
            "checks": {
                "redaction_integrity": {
                    "passed": checks["redaction_integrity"].get("passed"),
                    "privacy_violations": len(checks["redaction_integrity"].get("privacy_violations", [])),
                    "hallucinated_fields": len(checks["redaction_integrity"].get("hallucinated_fields", [])),
                },
                "greedy_matcher": {
                    "passed": checks["greedy_matcher"].get("passed"),
                    "match_rate": checks["greedy_matcher"].get("match_rate"),
                    "not_found_count": len(checks["greedy_matcher"].get("not_found", [])),
                },
                "pan_validation": {
                    "valid": checks["pan_validation"].get("valid"),
                    "skipped": checks["pan_validation"].get("skipped", False),
                },
                "aadhaar_validation": {
                    "valid": checks["aadhaar_validation"].get("valid"),
                    "checksum_passed": checks["aadhaar_validation"].get("checksum_passed"),
                    "is_masked": checks["aadhaar_validation"].get("is_masked"),
                    "skipped": checks["aadhaar_validation"].get("skipped", False),
                },
            },
            "elapsed_seconds": round(elapsed, 2),
        }
        result["node_results"] = existing_nr

        status = "CLEAN" if score < 20 else "SUSPICIOUS" if score < 60 else "HIGH_RISK"
        sub_summaries = []
        if not checks["redaction_integrity"].get("skipped"):
            sub_summaries.append(
                f"redaction={'PASS' if checks['redaction_integrity'].get('passed') else 'FAIL'}"
            )
        if not checks["greedy_matcher"].get("skipped"):
            sub_summaries.append(
                f"raw_match={'PASS' if checks['greedy_matcher'].get('passed') else 'FAIL'}"
                f"({checks['greedy_matcher'].get('match_rate', 0):.0%})"
            )
        if not checks["pan_validation"].get("skipped"):
            sub_summaries.append(
                f"PAN={'VALID' if checks['pan_validation'].get('valid') else 'INVALID'}"
            )
        if not checks["aadhaar_validation"].get("skipped"):
            sub_summaries.append(
                f"Aadhaar={'VALID' if checks['aadhaar_validation'].get('valid') else 'INVALID'}"
            )

        summary = (
            f"Node 3 [Document Intelligence] complete — "
            f"score={score}/100 ({status}), "
            f"{', '.join(sub_summaries) if sub_summaries else 'no checks applicable'}, "
            f"elapsed={elapsed:.2f}s"
        )
        logger.info(summary)
        result["messages"] = [AIMessage(content=summary)]

    except Exception as exc:
        elapsed = time.perf_counter() - t_start
        logger.error("Node 3 [Document Intelligence] crashed: %s", exc, exc_info=True)
        existing_nr = state.get("node_results") or {}
        existing_nr["document_intelligence"] = {
            "score": 0.0,
            "flags": [f"ERROR: {exc}"],
            "error": str(exc),
            "elapsed_seconds": round(elapsed, 2),
        }
        result["node_results"] = existing_nr
        result["intelligence_flags"] = [f"ERROR: {exc}"]
        result["messages"] = [
            AIMessage(content=f"Node 3 [Document Intelligence] — error: {exc}")
        ]

    return result
