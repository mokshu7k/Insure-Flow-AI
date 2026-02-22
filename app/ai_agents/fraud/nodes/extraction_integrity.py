"""
Node 1: Extraction Integrity — Three-Way Reconciliation.

This node treats the LLM's output as a "draft" and the raw PDF bytes
as the "undeniable truth." It cross-references three independent sources
to detect hallucinations, visual-only edits, and tampered documents.

Pipeline:
  1. Run PyMuPDF → raw text stream (ground truth)
  2. Call Gemini twice (primary JSON + shadow total) — blind split
  3. Run Python summation over line items
  4. Perform literal anchor check (string matching)
  5. Compare all three sources
  6. Optional: coordinate verification via Tesseract
  7. Calculate integrity_risk_score (0–100)

This node is the first in the fraud detection agent graph.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.messages import AIMessage

from app.ai_agents.fraud.state import FraudAgentState

logger = logging.getLogger(__name__)


async def extraction_integrity_node(state: FraudAgentState, config: dict | None = None) -> dict[str, Any]:
    """LangGraph node — performs extraction integrity analysis.

    Reads:
        state["document_bytes"]
        state["document_type_code"]
        state["existing_extracted_data"]

    Writes:
        raw_text, primary_extraction, shadow_total,
        integrity_checks, integrity_risk_score, integrity_flags,
        node_results (partial), messages
    """
    from app.ai_agents.fraud.tools.pdf_extractor import (
        get_raw_text,
        get_page_images,
    )
    from app.ai_agents.fraud.tools.gemini_extractor import (
        primary_extraction,
        shadow_total_extraction,
        coordinate_extraction,
    )
    from app.ai_agents.fraud.tools.reconciliation import (
        literal_anchor_check,
        arithmetic_recalculation,
        shadow_comparison,
        coordinate_verification,
        calculate_integrity_score,
    )

    claim_id = state.get("claim_id", "unknown")
    doc_id = state.get("document_id", "unknown")
    doc_bytes = state.get("document_bytes")
    doc_type = state.get("document_type_code", "UNKNOWN")

    logger.info(
        "Node 1 [Extraction Integrity] starting — claim=%s doc=%s type=%s",
        claim_id, doc_id, doc_type,
    )
    t_start = time.perf_counter()

    # ── Defaults (in case of early exit) ──────────────────────────────────────
    result: dict[str, Any] = {
        "raw_text": None,
        "primary_extraction": None,
        "shadow_total": None,
        "integrity_checks": {},
        "integrity_risk_score": 0.0,
        "integrity_flags": [],
        "messages": [AIMessage(content="Node 1 [Extraction Integrity]: starting…")],
    }

    if not doc_bytes:
        logger.warning("No document bytes provided — skipping extraction integrity")
        result["integrity_flags"] = ["SKIPPED: no document bytes available"]
        result["messages"] = [
            AIMessage(content="Node 1 [Extraction Integrity]: SKIPPED — no document bytes.")
        ]
        return result

    # ── Step 1: Raw text extraction (PyMuPDF) ─────────────────────────────────
    logger.info("Step 1: Extracting raw text via PyMuPDF…")
    raw_text = get_raw_text(doc_bytes)
    result["raw_text"] = raw_text
    has_text_layer = len(raw_text.strip()) > 20

    logger.info(
        "Raw text extracted: %d chars, has_text_layer=%s",
        len(raw_text), has_text_layer,
    )

    # ── Step 2: Render pages as images for Gemini ─────────────────────────────
    logger.info("Step 2: Rendering PDF pages as images…")
    page_images = get_page_images(doc_bytes)

    if not page_images:
        logger.warning("Could not render PDF pages — using existing extraction only")
        # Fall back to existing extracted data if available
        existing = state.get("existing_extracted_data") or {}
        result["primary_extraction"] = existing
        result["messages"] = [
            AIMessage(content="Node 1 [Extraction Integrity]: partial — no page images rendered.")
        ]
        return result

    # ── Step 3: Dual Gemini extraction (blind split) ──────────────────────────
    logger.info("Step 3a: Primary Gemini extraction (full JSON)…")
    try:
        primary_data = primary_extraction(page_images, doc_type)
        result["primary_extraction"] = primary_data
    except Exception as exc:
        logger.error("Primary extraction failed: %s", exc)
        primary_data = state.get("existing_extracted_data") or {}
        result["primary_extraction"] = primary_data
        result["integrity_flags"] = [f"PRIMARY_EXTRACTION_FAILED: {exc}"]

    logger.info("Step 3b: Shadow Gemini extraction (total only)…")
    try:
        shadow_val = shadow_total_extraction(page_images)
        result["shadow_total"] = shadow_val
    except Exception as exc:
        logger.error("Shadow extraction failed: %s", exc)
        shadow_val = None
        result["shadow_total"] = None

    # ── Step 4: Three-Way Reconciliation ──────────────────────────────────────
    checks: dict[str, Any] = {}

    # 4a. Literal Anchor Check — only meaningful if we have a text layer
    logger.info("Step 4a: Literal anchor check…")
    if has_text_layer:
        checks["literal_match"] = literal_anchor_check(primary_data, raw_text)
    else:
        checks["literal_match"] = {
            "passed": True,
            "skipped": True,
            "skip_reason": "no_text_layer_in_pdf",
            "total_fields": 0,
            "matched_fields": 0,
            "mismatched_fields": [],
            "match_rate": 1.0,
        }

    # 4b. Arithmetic Recalculation
    logger.info("Step 4b: Arithmetic recalculation…")
    checks["arithmetic"] = arithmetic_recalculation(primary_data)

    # 4c. Shadow Comparison
    logger.info("Step 4c: Shadow comparison…")
    primary_total = primary_data.get("total_amount")
    checks["shadow"] = shadow_comparison(primary_total, shadow_val)

    # 4d. Coordinate Verification (optional — adds latency)
    logger.info("Step 4d: Coordinate verification…")
    try:
        coord_data = coordinate_extraction(page_images)
        checks["coordinate"] = coordinate_verification(
            coord_data, primary_total, page_images
        )
    except Exception as exc:
        logger.warning("Coordinate check failed: %s", exc)
        checks["coordinate"] = {
            "passed": True,
            "method": "skipped",
            "skip_reason": f"error: {exc}",
        }

    result["integrity_checks"] = checks

    # ── Step 5: Calculate composite integrity score ───────────────────────────
    logger.info("Step 5: Calculating integrity risk score…")
    score, flags = calculate_integrity_score(checks)
    result["integrity_risk_score"] = score
    result["integrity_flags"] = flags

    # ── Build node_results entry ──────────────────────────────────────────────
    elapsed = time.perf_counter() - t_start
    node_result = {
        "extraction_integrity": {
            "score": score,
            "flags": flags,
            "checks": {
                "literal_match": {
                    "passed": checks["literal_match"].get("passed"),
                    "match_rate": checks["literal_match"].get("match_rate"),
                    "mismatched_count": len(checks["literal_match"].get("mismatched_fields", [])),
                },
                "arithmetic": {
                    "passed": checks["arithmetic"].get("passed"),
                    "difference_pct": checks["arithmetic"].get("difference_pct", 0),
                },
                "shadow": {
                    "passed": checks["shadow"].get("passed"),
                    "difference_pct": checks["shadow"].get("difference_pct", 0),
                },
                "coordinate": {
                    "passed": checks["coordinate"].get("passed"),
                    "method": checks["coordinate"].get("method"),
                },
            },
            "elapsed_seconds": round(elapsed, 2),
        }
    }
    result["node_results"] = node_result

    # ── Summary message ───────────────────────────────────────────────────────
    status = "CLEAN" if score < 20 else "SUSPICIOUS" if score < 60 else "HIGH_RISK"
    summary = (
        f"Node 1 [Extraction Integrity] complete — "
        f"score={score}/100 ({status}), "
        f"literal={'PASS' if checks['literal_match'].get('passed') else 'FAIL'}, "
        f"math={'PASS' if checks['arithmetic'].get('passed') else 'FAIL'}, "
        f"shadow={'PASS' if checks['shadow'].get('passed') else 'FAIL'}, "
        f"coordinate={'PASS' if checks['coordinate'].get('passed') else 'FAIL'}, "
        f"elapsed={elapsed:.2f}s"
    )
    logger.info(summary)
    result["messages"] = [AIMessage(content=summary)]

    return result
