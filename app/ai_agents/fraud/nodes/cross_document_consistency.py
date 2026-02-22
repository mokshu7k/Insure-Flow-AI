"""
Node 2: Cross-Document Consistency — the "Story of the Claim" validator.

Ensures that multiple documents uploaded for the same claim tell a
logically consistent story.  All checks are deterministic (no LLM).

Sub-checks:
  1. Canonical Field Promotion  (data preparation)
  2. Date Overlap & Timeline Validator
  3. Entity Name Equality (strict + fuzzy via thefuzz)
  4. Policy Window Alignment
  5. Financial Sum-of-Parts Check
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from langchain_core.messages import AIMessage

from app.ai_agents.fraud.state import FraudAgentState

logger = logging.getLogger(__name__)

# ── Risk weights ──────────────────────────────────────────────────────────────
RISK_WEIGHTS = {
    "timeline_violation":   90,
    "name_mismatch":       80,
    "date_mismatch":       70,
    "policy_window_breach": 85,
    "financial_mismatch":   75,
}

# Document types that carry financial amounts for sum-of-parts
_FINANCIAL_DOC_TYPES = {
    "HOSPITAL_BILL", "PHARMACY_BILL", "LAB_REPORT", "AMBULANCE_RECEIPT",
}

# The "main" bill doc type — its total is the grand total to compare against
_MAIN_BILL_TYPE = "HOSPITAL_BILL"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v))
    s = str(v).replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


# ── Sub-check 1: Canonical Field Promotion ────────────────────────────────────

def _promote_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Promote a document's extracted_data into canonical fields.

    Uses the same PROMOTED_FIELD_MAP from extraction_service.
    """
    from app.services.extraction_service import promote_fields

    doc_type = doc.get("document_type_code", "")
    extracted = doc.get("extracted_data") or {}
    promoted = promote_fields(doc_type, extracted)

    return {
        "document_id": doc.get("document_id", "unknown"),
        "document_type_code": doc_type,
        "promoted": promoted,
        "extracted_data": extracted,
    }


# ── Sub-check 2: Timeline Validator ──────────────────────────────────────────

def _check_timeline(promoted_docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate the chronological timeline across all documents.

    Rules:
      admission_date ≤ document_date (any receipt) ≤ discharge_date
      admission_date ≤ discharge_date
    """
    flags: list[str] = []
    details: list[dict[str, Any]] = []

    # Collect dates
    admission_dates: list[tuple[str, date]] = []
    discharge_dates: list[tuple[str, date]] = []
    document_dates: list[tuple[str, date, str]] = []  # (doc_id, date, type)

    for doc in promoted_docs:
        p = doc["promoted"]
        doc_label = f"{doc['document_type_code']}({doc['document_id'][:8]})"

        ad = _parse_date(p.get("admission_date"))
        dd = _parse_date(p.get("discharge_date"))
        docdate = _parse_date(p.get("document_date"))

        if ad:
            admission_dates.append((doc_label, ad))
        if dd:
            discharge_dates.append((doc_label, dd))
        if docdate:
            document_dates.append((doc_label, docdate, doc["document_type_code"]))

    # Check admission ≤ discharge
    for ad_label, ad in admission_dates:
        for dd_label, dd in discharge_dates:
            if ad > dd:
                flags.append(
                    f"TIMELINE: admission ({ad_label}: {ad}) > discharge ({dd_label}: {dd})"
                )
                details.append({
                    "check": "admission_before_discharge",
                    "passed": False,
                    "admission": str(ad),
                    "discharge": str(dd),
                })

    # Check document_dates fall within admission–discharge window
    if admission_dates and discharge_dates:
        earliest_admission = min(d for _, d in admission_dates)
        latest_discharge = max(d for _, d in discharge_dates)

        for doc_label, docdate, doc_type in document_dates:
            if docdate < earliest_admission:
                flags.append(
                    f"TIMELINE: {doc_label} date ({docdate}) is before admission ({earliest_admission})"
                )
                details.append({
                    "check": "doc_date_before_admission",
                    "passed": False,
                    "doc_date": str(docdate),
                    "admission": str(earliest_admission),
                    "document": doc_label,
                })
            elif docdate > latest_discharge:
                # Receipts after discharge are suspicious but pharmacy can be day-of
                gap_days = (docdate - latest_discharge).days
                if gap_days > 1:  # 1-day grace for discharge-day receipts
                    flags.append(
                        f"TIMELINE_GAP: {doc_label} date ({docdate}) is {gap_days}d after "
                        f"discharge ({latest_discharge})"
                    )
                    details.append({
                        "check": "doc_date_after_discharge",
                        "passed": False,
                        "doc_date": str(docdate),
                        "discharge": str(latest_discharge),
                        "gap_days": gap_days,
                        "document": doc_label,
                    })

    return {
        "passed": len(flags) == 0,
        "flags": flags,
        "details": details,
        "admission_dates": [(l, str(d)) for l, d in admission_dates],
        "discharge_dates": [(l, str(d)) for l, d in discharge_dates],
        "document_dates": [(l, str(d), t) for l, d, t in document_dates],
    }


# ── Sub-check 3: Entity Name Equality ────────────────────────────────────────

def _check_entity_names(promoted_docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Cross-check patient_name, hospital_name, doctor_name across docs."""
    from app.ai_agents.fraud.tools.name_matcher import compare_names

    fields_to_check = ["patient_name", "hospital_name", "doctor_name"]
    comparisons: list[dict[str, Any]] = []
    flags: list[str] = []

    for field in fields_to_check:
        # Collect all (doc_label, value) pairs for this field
        values: list[tuple[str, str]] = []
        for doc in promoted_docs:
            val = doc["promoted"].get(field)
            if val:
                label = f"{doc['document_type_code']}({doc['document_id'][:8]})"
                values.append((label, str(val)))

        if len(values) < 2:
            continue

        # Compare all pairs
        for i in range(len(values)):
            for j in range(i + 1, len(values)):
                label_a, name_a = values[i]
                label_b, name_b = values[j]
                result = compare_names(name_a, name_b, label_a, label_b)
                result["field"] = field
                comparisons.append(result)

                if result["verdict"] == "IDENTITY_MISMATCH":
                    flags.append(
                        f"NAME_MISMATCH({field}): {label_a} '{name_a}' ≠ "
                        f"{label_b} '{name_b}' (fuzzy={result['fuzzy_score']:.2f})"
                    )
                elif result["verdict"] == "MINOR_WARNING":
                    flags.append(
                        f"NAME_VARIANT({field}): {label_a} '{name_a}' ~ "
                        f"{label_b} '{name_b}' (fuzzy={result['fuzzy_score']:.2f})"
                    )

    return {
        "passed": all(c["verdict"] != "IDENTITY_MISMATCH" for c in comparisons),
        "comparisons": comparisons,
        "flags": flags,
    }


# ── Sub-check 4: Policy Window Alignment ─────────────────────────────────────

def _check_policy_window(
    promoted_docs: list[dict[str, Any]],
    policy_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Verify all extracted dates fall within the policy validity window."""
    if not policy_data:
        return {
            "passed": True,
            "skipped": True,
            "skip_reason": "no_policy_data",
            "flags": [],
        }

    policy_start = _parse_date(policy_data.get("start_date"))
    policy_end = _parse_date(policy_data.get("end_date"))

    if not policy_start and not policy_end:
        return {
            "passed": True,
            "skipped": True,
            "skip_reason": "no_policy_dates",
            "flags": [],
        }

    flags: list[str] = []
    details: list[dict[str, Any]] = []

    date_fields = ["admission_date", "discharge_date", "document_date"]

    for doc in promoted_docs:
        doc_label = f"{doc['document_type_code']}({doc['document_id'][:8]})"
        p = doc["promoted"]

        for field in date_fields:
            d = _parse_date(p.get(field))
            if d is None:
                continue

            if policy_start and d < policy_start:
                flags.append(
                    f"POLICY_BREACH: {doc_label}.{field} ({d}) is before "
                    f"policy start ({policy_start})"
                )
                details.append({
                    "document": doc_label,
                    "field": field,
                    "date": str(d),
                    "policy_start": str(policy_start),
                    "breach": "before_start",
                })

            if policy_end and d > policy_end:
                flags.append(
                    f"POLICY_BREACH: {doc_label}.{field} ({d}) is after "
                    f"policy expiry ({policy_end})"
                )
                details.append({
                    "document": doc_label,
                    "field": field,
                    "date": str(d),
                    "policy_end": str(policy_end),
                    "breach": "after_expiry",
                })

    return {
        "passed": len(flags) == 0,
        "flags": flags,
        "details": details,
        "policy_start": str(policy_start) if policy_start else None,
        "policy_end": str(policy_end) if policy_end else None,
    }


# ── Sub-check 5: Financial Sum-of-Parts ──────────────────────────────────────

def _check_financial_sum(promoted_docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate receipt totals and compare against the main bill's grand total.

    If Σ(individual receipts) > grand_total → double-billing / inflation.
    """
    receipt_totals: list[tuple[str, Decimal]] = []
    grand_total: Decimal | None = None
    grand_total_doc: str = ""

    for doc in promoted_docs:
        doc_label = f"{doc['document_type_code']}({doc['document_id'][:8]})"
        amount = _parse_amount(doc["promoted"].get("total_amount"))

        if amount is None:
            continue

        if doc["document_type_code"] == _MAIN_BILL_TYPE:
            grand_total = amount
            grand_total_doc = doc_label
        else:
            if doc["document_type_code"] in _FINANCIAL_DOC_TYPES:
                receipt_totals.append((doc_label, amount))

    if grand_total is None or len(receipt_totals) == 0:
        return {
            "passed": True,
            "skipped": True,
            "skip_reason": "insufficient_financial_data",
            "flags": [],
        }

    receipt_sum = sum(a for _, a in receipt_totals)
    difference = receipt_sum - grand_total
    diff_pct = float(difference / grand_total * 100) if grand_total > 0 else 0.0

    flags: list[str] = []

    # If sub-receipts exceed the main bill by more than 5%
    if difference > 0 and diff_pct > 5.0:
        flags.append(
            f"FINANCIAL_INFLATION: receipts sum ({receipt_sum}) exceeds "
            f"main bill ({grand_total_doc}: {grand_total}) by {diff_pct:.1f}%"
        )

    return {
        "passed": len(flags) == 0,
        "grand_total": str(grand_total),
        "grand_total_doc": grand_total_doc,
        "receipt_sum": str(receipt_sum),
        "receipt_count": len(receipt_totals),
        "receipts": [(l, str(a)) for l, a in receipt_totals],
        "difference": str(difference),
        "difference_pct": round(diff_pct, 2),
        "flags": flags,
    }


# ── Score calculation ─────────────────────────────────────────────────────────

def _calculate_consistency_score(checks: dict[str, dict[str, Any]]) -> tuple[float, list[str]]:
    """Calculate cross-document consistency risk score (0–100)."""
    penalties: list[float] = []
    all_flags: list[str] = []

    # Timeline
    timeline = checks.get("timeline", {})
    if not timeline.get("passed", True) and not timeline.get("skipped"):
        n_flags = len(timeline.get("flags", []))
        penalty = min(RISK_WEIGHTS["timeline_violation"], 30 * n_flags)
        penalties.append(penalty)
        all_flags.extend(timeline.get("flags", []))

    # Name matching
    names = checks.get("entity_names", {})
    if not names.get("passed", True):
        identity_mismatches = sum(
            1 for c in names.get("comparisons", [])
            if c.get("verdict") == "IDENTITY_MISMATCH"
        )
        penalty = min(100, RISK_WEIGHTS["name_mismatch"] * identity_mismatches)
        penalties.append(penalty)
    all_flags.extend(names.get("flags", []))

    # Date mismatch (from name_matcher date comparisons embedded in entity check)
    # This is handled via timeline already

    # Policy window
    policy = checks.get("policy_window", {})
    if not policy.get("passed", True) and not policy.get("skipped"):
        n_breaches = len(policy.get("flags", []))
        penalty = min(100, RISK_WEIGHTS["policy_window_breach"] * n_breaches)
        penalties.append(penalty)
        all_flags.extend(policy.get("flags", []))

    # Financial
    financial = checks.get("financial_sum", {})
    if not financial.get("passed", True) and not financial.get("skipped"):
        diff_pct = financial.get("difference_pct", 0)
        severity = min(1.0, diff_pct / 20.0)
        penalty = RISK_WEIGHTS["financial_mismatch"] * severity
        penalties.append(penalty)
        all_flags.extend(financial.get("flags", []))

    if not penalties:
        return 0.0, all_flags

    max_penalty = max(penalties)
    others = sum(p for p in penalties if p != max_penalty)
    additional = min(20.0, others * 0.3)
    score = min(100.0, max_penalty + additional)

    return round(score, 1), all_flags


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  THE NODE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def cross_document_consistency_node(
    state: FraudAgentState,
    config: dict | None = None,
) -> dict[str, Any]:
    """LangGraph node — cross-document consistency analysis.

    Reads:
        state["all_documents_data"]  — list of {document_id, document_type_code,
                                        extracted_data} for ALL docs on the claim
        state["policy_data"]         — {start_date, end_date, sum_insured}

    Writes:
        consistency_checks, consistency_risk_score, consistency_flags,
        node_results (partial), messages
    """
    claim_id = state.get("claim_id", "unknown")
    all_docs = state.get("all_documents_data") or []
    policy_data = state.get("policy_data")

    logger.info(
        "Node 2 [Cross-Document Consistency] starting — claim=%s, docs=%d",
        claim_id, len(all_docs),
    )
    t_start = time.perf_counter()

    result: dict[str, Any] = {
        "consistency_checks": {},
        "consistency_risk_score": 0.0,
        "consistency_flags": [],
    }

    if len(all_docs) < 2:
        logger.info("Fewer than 2 documents — skipping cross-document checks")
        result["consistency_flags"] = ["SKIPPED: fewer than 2 documents"]
        result["messages"] = [
            AIMessage(content="Node 2 [Cross-Document Consistency]: SKIPPED — fewer than 2 documents.")
        ]
        # Merge into node_results
        existing_nr = state.get("node_results") or {}
        existing_nr["cross_document_consistency"] = {
            "score": 0.0,
            "flags": result["consistency_flags"],
            "skipped": True,
        }
        result["node_results"] = existing_nr
        return result

    try:
        # Step 1: Canonical Field Promotion
        logger.info("Step 1: Promoting canonical fields for %d documents…", len(all_docs))
        promoted_docs = [_promote_document(doc) for doc in all_docs]

        checks: dict[str, Any] = {}

        # Step 2: Timeline validation
        logger.info("Step 2: Timeline validation…")
        checks["timeline"] = _check_timeline(promoted_docs)

        # Step 3: Entity name equality
        logger.info("Step 3: Entity name equality…")
        checks["entity_names"] = _check_entity_names(promoted_docs)

        # Step 4: Policy window alignment
        logger.info("Step 4: Policy window alignment…")
        checks["policy_window"] = _check_policy_window(promoted_docs, policy_data)

        # Step 5: Financial sum-of-parts
        logger.info("Step 5: Financial sum-of-parts…")
        checks["financial_sum"] = _check_financial_sum(promoted_docs)

        result["consistency_checks"] = checks

        # Calculate composite score
        score, flags = _calculate_consistency_score(checks)
        result["consistency_risk_score"] = score
        result["consistency_flags"] = flags

        elapsed = time.perf_counter() - t_start

        # Merge into node_results
        existing_nr = state.get("node_results") or {}
        existing_nr["cross_document_consistency"] = {
            "score": score,
            "flags": flags,
            "checks": {
                "timeline": {
                    "passed": checks["timeline"].get("passed"),
                    "flag_count": len(checks["timeline"].get("flags", [])),
                },
                "entity_names": {
                    "passed": checks["entity_names"].get("passed"),
                    "comparisons": len(checks["entity_names"].get("comparisons", [])),
                },
                "policy_window": {
                    "passed": checks["policy_window"].get("passed"),
                    "skipped": checks["policy_window"].get("skipped", False),
                },
                "financial_sum": {
                    "passed": checks["financial_sum"].get("passed"),
                    "skipped": checks["financial_sum"].get("skipped", False),
                    "difference_pct": checks["financial_sum"].get("difference_pct", 0),
                },
            },
            "elapsed_seconds": round(elapsed, 2),
        }
        result["node_results"] = existing_nr

        status = "CLEAN" if score < 20 else "SUSPICIOUS" if score < 60 else "HIGH_RISK"
        summary = (
            f"Node 2 [Cross-Document Consistency] complete — "
            f"score={score}/100 ({status}), "
            f"timeline={'PASS' if checks['timeline'].get('passed') else 'FAIL'}, "
            f"names={'PASS' if checks['entity_names'].get('passed') else 'FAIL'}, "
            f"policy={'PASS' if checks['policy_window'].get('passed') else 'SKIP/FAIL'}, "
            f"financial={'PASS' if checks['financial_sum'].get('passed') else 'SKIP/FAIL'}, "
            f"elapsed={elapsed:.2f}s"
        )
        logger.info(summary)
        result["messages"] = [AIMessage(content=summary)]

    except Exception as exc:
        elapsed = time.perf_counter() - t_start
        logger.error("Node 2 [Cross-Document Consistency] crashed: %s", exc, exc_info=True)
        existing_nr = state.get("node_results") or {}
        existing_nr["cross_document_consistency"] = {
            "score": 0.0,
            "flags": [f"ERROR: {exc}"],
            "error": str(exc),
            "elapsed_seconds": round(elapsed, 2),
        }
        result["node_results"] = existing_nr
        result["consistency_flags"] = [f"ERROR: {exc}"]
        result["messages"] = [
            AIMessage(content=f"Node 2 [Cross-Document Consistency] — error: {exc}")
        ]

    return result
