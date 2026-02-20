"""
Layer 4 — Document Consistency Analysis
Uses extracted_data (from LangExtract/extract-thinker) to check
field consistency, date logic, and amount reconciliation.
"""
from __future__ import annotations

from typing import Any


def run(context: dict[str, Any]) -> dict[str, Any]:
    flags: list[str] = []
    score = 0.0

    extracted = context.get("extracted_data") or {}
    claim_amount = float(context.get("claim_amount", 0))
    claim_type = context.get("claim_type", "")

    # Check 1: Extraction confidence — if low, flag for manual review
    confidence = float(extracted.get("confidence", 1.0))
    if confidence < 0.5:
        flags.append(f"LOW_EXTRACTION_CONFIDENCE:{confidence:.2f}")
        score = max(score, 0.35)

    # Check 2: Amount mismatch between claim and document
    doc_amount = _extract_amount(extracted)
    if doc_amount and claim_amount:
        diff_pct = abs(doc_amount - claim_amount) / max(claim_amount, 1.0)
        if diff_pct > 0.20:
            flags.append(f"AMOUNT_MISMATCH_DOC_VS_CLAIM:{diff_pct:.1%}")
            score = max(score, 0.65)
        elif diff_pct > 0.10:
            flags.append(f"AMOUNT_MISMATCH_MINOR:{diff_pct:.1%}")
            score = max(score, 0.40)

    # Check 3: Date consistency
    service_date_str = extracted.get("fields", {}).get("date_of_service")
    claim_date_str = context.get("claim_created_at")
    if service_date_str and claim_date_str:
        import datetime
        try:
            service_date = datetime.date.fromisoformat(service_date_str[:10])
            claim_date = datetime.date.fromisoformat(str(claim_date_str)[:10])
            if service_date > claim_date:
                flags.append("SERVICE_DATE_AFTER_CLAIM_DATE")
                score = max(score, 0.80)
        except (ValueError, TypeError):
            pass

    # Check 4: Missing critical fields
    expected_fields = _expected_fields_for_type(claim_type)
    doc_fields = set(extracted.get("fields", {}).keys())
    missing = expected_fields - doc_fields
    if len(missing) > 2:
        flags.append(f"MISSING_CRITICAL_FIELDS:{missing}")
        score = max(score, 0.30)

    return {"score": min(score, 1.0), "flags": flags, "layer": "document"}


def _extract_amount(extracted: dict) -> float | None:
    fields = extracted.get("fields", {})
    for key in ("total_amount", "bill_amount", "invoice_amount", "amount"):
        val = fields.get(key)
        if val is not None:
            try:
                return float(str(val).replace(",", "").replace("₹", "").strip())
            except ValueError:
                pass
    return None


def _expected_fields_for_type(claim_type: str) -> set[str]:
    base = {"date_of_service", "provider_name", "total_amount"}
    extras = {
        "HEALTH": {"diagnosis", "patient_name"},
        "MOTOR": {"vehicle_number", "repair_estimate"},
        "REIMBURSEMENT": {"receipt_number"},
        "CASHLESS": {"preauth_number", "hospital_name"},
    }
    return base | extras.get(claim_type, set())
