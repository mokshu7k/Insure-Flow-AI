"""
Node 5: Document Content Fraud — Gemini-Powered Deep Analysis.

Combines *deterministic* arithmetic / GST validation with *Gemini's*
medical knowledge to detect content-level fraud in insurance documents.

Pipeline:
  1. Arithmetic validator  (line-item sums, qty×rate)    [deterministic]
  2. GST validator (tax-slab + GSTIN format)              [deterministic]
  3. Gemini content analyser (medical plausibility, pricing, drug-diagnosis)
  4. Multi-document diagnosis consistency                  [deterministic]
  5. Score calculation (max-dominant + Gemini blend)

Sits at the end of the sequential chain:
    Node 1 → Node 2 → Node 3 → **Node 5** → aggregator
"""
from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.messages import AIMessage

from app.ai_agents.fraud.state import FraudAgentState

logger = logging.getLogger(__name__)

# Severity → risk-weight mapping for Gemini signals
_SEVERITY_WEIGHTS: dict[str, int] = {
    "CRITICAL": 95,
    "HIGH":     75,
    "MEDIUM":   50,
    "LOW":      25,
}


def _calculate_content_fraud_score(
    arithmetic_flags: list[str],
    gst_flags: list[str],
    gemini_signals: list[dict],
    gemini_risk_score: int,
) -> tuple[float, list[str]]:
    """Combine deterministic + Gemini signals into a single score & flags list."""
    penalties: list[float] = []
    all_flags: list[str] = []

    # ── Arithmetic penalties ──────────────────────────────────────────────
    for flag in arithmetic_flags:
        if "ARITHMETIC_MISMATCH" in flag:
            penalties.append(70)
        elif "LINE_ITEM_MATH_ERROR" in flag:
            penalties.append(55)
        elif "TOTAL_DECOMPOSITION_ERROR" in flag:
            penalties.append(65)
        all_flags.append(flag)

    # ── GST penalties ─────────────────────────────────────────────────────
    for flag in gst_flags:
        if "GST_RATE_ANOMALY" in flag:
            penalties.append(50)
        elif "CGST_SGST_MISMATCH" in flag:
            penalties.append(45)
        elif "GSTIN_FORMAT_INVALID" in flag:
            penalties.append(40)
        all_flags.append(flag)

    # ── Gemini signal penalties ───────────────────────────────────────────
    for sig in gemini_signals:
        severity = sig.get("severity", "LOW").upper()
        weight = _SEVERITY_WEIGHTS.get(severity, 25)
        penalties.append(weight)
        category = sig.get("category", "GENERAL")
        all_flags.append(
            f"CONTENT_{severity}: [{category}] {sig.get('signal', 'unknown')}"
        )

    if not penalties:
        return 0.0, all_flags

    # Max-dominant scoring
    max_p = max(penalties)
    others = sum(p for p in penalties if p != max_p)
    deterministic_score = min(100.0, max_p + min(25.0, others * 0.15))

    # Blend with Gemini's own risk_score (60/40)
    if gemini_risk_score > 0:
        final = 0.6 * deterministic_score + 0.4 * gemini_risk_score
    else:
        final = deterministic_score

    return round(min(100.0, final), 1), all_flags


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def document_content_fraud_node(
    state: FraudAgentState,
    config: dict | None = None,
) -> dict[str, Any]:
    """LangGraph node — document content fraud analysis.

    Reads
    -----
    state["primary_extraction"] *or* state["existing_extracted_data"]
    state["document_type_code"]
    state["all_documents_data"]

    Writes
    ------
    content_fraud_checks, content_fraud_risk_score, content_fraud_flags,
    node_results (partial), messages
    """
    from app.ai_agents.fraud.tools.arithmetic_gst_validator import (
        validate_arithmetic,
        validate_gst,
    )
    from app.ai_agents.fraud.tools.gemini_content_analyzer import (
        analyze_document_content,
    )

    claim_id = state.get("claim_id", "unknown")
    doc_id   = state.get("document_id", "unknown")
    doc_type = state.get("document_type_code", "UNKNOWN")

    logger.info(
        "Node 5 [Document Content Fraud] starting — claim=%s doc=%s type=%s",
        claim_id, doc_id, doc_type,
    )
    t0 = time.perf_counter()

    # ── Defaults ──────────────────────────────────────────────────────────────
    result: dict[str, Any] = {
        "content_fraud_checks": {},
        "content_fraud_risk_score": 0.0,
        "content_fraud_flags": [],
        "node_results": {},
        "messages": [],
    }

    # Prefer Node-1's fresh extraction; fall back to existing
    extracted = (
        state.get("primary_extraction")
        or state.get("existing_extracted_data")
    )

    if not extracted:
        logger.warning("Node 5: no extracted data — skipping")
        result["content_fraud_flags"] = ["SKIPPED: no extracted data available"]
        result["content_fraud_checks"] = {"skipped": True}
        result["node_results"] = {
            "document_content_fraud": {
                "score": 0.0,
                "flags": ["SKIPPED: no extracted data"],
                "details": {"skipped": True},
            }
        }
        result["messages"] = [
            AIMessage(content="Node 5 [Content Fraud] — skipped (no extracted data)")
        ]
        return result

    checks: dict[str, Any] = {}
    arith_flags: list[str] = []
    gst_flags: list[str] = []

    # ── Step 1: Arithmetic validation ─────────────────────────────────────────
    try:
        arith = validate_arithmetic(extracted)
        checks["arithmetic"] = arith
        arith_flags = arith.get("flags", [])
    except Exception as exc:
        logger.error("Node 5: arithmetic check failed — %s", exc)
        checks["arithmetic"] = {"error": str(exc)}

    # ── Step 2: GST validation ────────────────────────────────────────────────
    try:
        gst = validate_gst(extracted)
        checks["gst"] = gst
        gst_flags = gst.get("flags", [])
    except Exception as exc:
        logger.error("Node 5: GST check failed — %s", exc)
        checks["gst"] = {"error": str(exc)}

    # ── Step 3: Gemini content analysis ───────────────────────────────────────
    gemini_signals: list[dict] = []
    gemini_risk_score = 0
    gemini_summary = ""

    try:
        gemini = await analyze_document_content(
            document_type=doc_type,
            extracted_data=extracted,
            arithmetic_results=checks.get("arithmetic"),
            gst_results=checks.get("gst"),
        )
        checks["gemini_analysis"] = gemini
        gemini_signals   = gemini.get("signals", [])
        gemini_risk_score = gemini.get("risk_score", 0)
        gemini_summary   = gemini.get("summary", "")
        checks["medical_plausibility"] = gemini.get("medical_plausibility", "UNKNOWN")
    except Exception as exc:
        logger.error("Node 5: Gemini analysis failed — %s", exc)
        checks["gemini_analysis"] = {"error": str(exc)}

    # ── Step 4: Multi-document diagnosis consistency ──────────────────────────
    all_docs = state.get("all_documents_data") or []
    if len(all_docs) > 1:
        diagnoses: set[str] = set()
        for doc in all_docs:
            ext = doc.get("extracted_data") or {}
            diag = (
                ext.get("diagnosis")
                or ext.get("primary_diagnosis")
                or ext.get("clinical_diagnosis")
            )
            if diag:
                diagnoses.add(str(diag).strip().lower())
        if len(diagnoses) > 1:
            arith_flags.append(
                f"DIAGNOSIS_VARIATION: {len(diagnoses)} different diagnosis "
                "descriptions across documents"
            )
            checks["diagnosis_consistency"] = {
                "unique_diagnoses": sorted(diagnoses),
                "consistent": False,
            }
        elif diagnoses:
            checks["diagnosis_consistency"] = {
                "diagnosis": next(iter(diagnoses)),
                "consistent": True,
            }

    # ── Score calculation ─────────────────────────────────────────────────────
    score, all_flags = _calculate_content_fraud_score(
        arithmetic_flags=arith_flags,
        gst_flags=gst_flags,
        gemini_signals=gemini_signals,
        gemini_risk_score=gemini_risk_score,
    )

    elapsed = time.perf_counter() - t0
    summary = (
        f"Node 5 [Content Fraud] — score={score}, "
        f"flags={len(all_flags)}, gemini=\"{gemini_summary}\", "
        f"time={elapsed:.1f}s"
    )
    logger.info(summary)

    result["content_fraud_checks"]     = checks
    result["content_fraud_risk_score"] = score
    result["content_fraud_flags"]      = all_flags
    result["node_results"] = {
        "document_content_fraud": {
            "score": score,
            "flags": all_flags,
            "details": checks,
        }
    }
    result["messages"] = [AIMessage(content=summary)]
    return result
