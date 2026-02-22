"""
Arithmetic & GST Validator — deterministic bill verification.

Recomputes line-item totals, validates GST rates against standard Indian
slabs (0 %, 5 %, 12 %, 18 %, 28 %), and checks tax break-down integrity.
Zero LLM calls — pure Python maths.
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)

# ── Standard Indian GST rates (%) ────────────────────────────────────────────
_VALID_GST_RATES = {0, 5, 12, 18, 28}
_GST_TOLERANCE_PCT = 1.5          # allow 1.5 % deviation for rounding
_AMOUNT_TOLERANCE = Decimal("2")  # ₹2 tolerance for rounding issues


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_decimal(v: Any) -> Decimal | None:
    """Convert any common amount representation to Decimal."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    s = (
        str(v)
        .replace(",", "")
        .replace("₹", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace("INR", "")
        .strip()
    )
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


# ── Arithmetic Validation ─────────────────────────────────────────────────────

def validate_arithmetic(extracted_data: dict[str, Any]) -> dict[str, Any]:
    """Validate arithmetic consistency of a bill / invoice.

    Checks
    ------
    1. ``sum(line_items) ≈ stated_subtotal_or_total``
    2. ``qty × rate ≈ amount`` for each line item
    3. ``subtotal + tax ≈ grand_total``

    Returns dict with ``flags`` list and per-check results.
    """
    flags: list[str] = []
    checks: dict[str, Any] = {}

    line_items = extracted_data.get("line_items", [])

    # Pull candidate total fields
    stated_total = _safe_decimal(
        extracted_data.get("total_amount")
        or extracted_data.get("grand_total")
        or extracted_data.get("amount_payable")
        or extracted_data.get("net_amount")
    )
    stated_subtotal = _safe_decimal(
        extracted_data.get("subtotal")
        or extracted_data.get("base_amount")
    )
    stated_tax = _safe_decimal(
        extracted_data.get("gst_amount")
        or extracted_data.get("tax_amount")
        or extracted_data.get("cgst_sgst_total")
    )

    # ── 1. Line-item summation ────────────────────────────────────────────
    if line_items:
        computed_sum = Decimal("0")
        item_errors: list[str] = []

        for idx, item in enumerate(line_items):
            amount = _safe_decimal(
                item.get("amount") or item.get("total") or item.get("price")
            )
            if amount is not None:
                computed_sum += amount

            # qty × rate check
            qty = _safe_decimal(item.get("quantity") or item.get("qty"))
            rate = _safe_decimal(item.get("rate") or item.get("unit_price"))
            if qty and rate and amount:
                expected = qty * rate
                if abs(expected - amount) > _AMOUNT_TOLERANCE:
                    item_errors.append(
                        f"Item {idx + 1}: {qty}×{rate}=₹{expected} but stated ₹{amount}"
                    )

        checks["line_item_sum"] = {
            "computed": float(computed_sum),
            "item_count": len(line_items),
            "item_errors": item_errors,
        }

        if item_errors:
            flags.append(
                f"LINE_ITEM_MATH_ERROR: {len(item_errors)} line item(s) "
                "have qty×rate ≠ amount"
            )

        # Compare to stated total / subtotal
        compare_target = stated_subtotal or stated_total
        if compare_target and computed_sum > 0:
            diff = abs(computed_sum - compare_target)
            if diff > _AMOUNT_TOLERANCE:
                pct = float(diff / compare_target * 100)
                checks["total_mismatch"] = {
                    "computed": float(computed_sum),
                    "stated": float(compare_target),
                    "difference": float(diff),
                    "difference_pct": round(pct, 2),
                }
                flags.append(
                    f"ARITHMETIC_MISMATCH: line items sum (₹{computed_sum:,.2f}) ≠ "
                    f"stated total (₹{compare_target:,.2f}), diff={pct:.1f}%"
                )

    # ── 2. Total decomposition: subtotal + tax ≈ grand total ──────────────
    if stated_subtotal and stated_tax and stated_total:
        expected_total = stated_subtotal + stated_tax
        diff = abs(expected_total - stated_total)
        if diff > _AMOUNT_TOLERANCE:
            checks["decomposition_error"] = {
                "subtotal": float(stated_subtotal),
                "tax": float(stated_tax),
                "expected_total": float(expected_total),
                "stated_total": float(stated_total),
            }
            flags.append(
                f"TOTAL_DECOMPOSITION_ERROR: subtotal(₹{stated_subtotal})"
                f"+tax(₹{stated_tax})=₹{expected_total} but total stated as ₹{stated_total}"
            )

    checks["flags"] = flags
    return checks


# ── GST Validation ────────────────────────────────────────────────────────────

def validate_gst(extracted_data: dict[str, Any]) -> dict[str, Any]:
    """Validate GST rates against standard Indian slabs.

    Medical services are typically at 5 % or 18 %.
    Medicines at 5 % or 12 %.
    Hospital room rent (> ₹5 000/day) at 5 %.

    Returns dict with ``flags`` list, ``computed_gst_rate``, etc.
    """
    flags: list[str] = []
    checks: dict[str, Any] = {}

    stated_tax = _safe_decimal(
        extracted_data.get("gst_amount")
        or extracted_data.get("tax_amount")
        or extracted_data.get("cgst_sgst_total")
    )
    base = _safe_decimal(
        extracted_data.get("subtotal")
        or extracted_data.get("base_amount")
    )

    # Explicit CGST / SGST / IGST
    cgst = _safe_decimal(extracted_data.get("cgst"))
    sgst = _safe_decimal(extracted_data.get("sgst"))
    igst = _safe_decimal(extracted_data.get("igst"))

    if cgst and sgst:
        if abs(cgst - sgst) > Decimal("0.5"):
            flags.append(
                f"CGST_SGST_MISMATCH: CGST(₹{cgst}) ≠ SGST(₹{sgst})"
            )
        stated_tax = cgst + sgst
    elif igst:
        stated_tax = igst

    if stated_tax and base and base > 0:
        gst_pct = float(stated_tax / base * 100)
        checks["computed_gst_rate"] = round(gst_pct, 2)
        checks["base_amount"] = float(base)
        checks["tax_amount"] = float(stated_tax)

        closest_slab = min(_VALID_GST_RATES, key=lambda s: abs(s - gst_pct))
        deviation = abs(gst_pct - closest_slab)

        if deviation > _GST_TOLERANCE_PCT:
            flags.append(
                f"GST_RATE_ANOMALY: computed GST rate {gst_pct:.1f}% doesn't match "
                f"any standard slab {sorted(_VALID_GST_RATES)}. Closest: {closest_slab}%"
            )

        checks["closest_standard_slab"] = closest_slab
        checks["deviation_from_slab"] = round(deviation, 2)
    else:
        checks["skipped"] = True
        checks["reason"] = "Missing tax or base amount in extracted data"

    # GSTIN format validation  (2-digit state + PAN + 1Z + check-digit)
    gstin = extracted_data.get("gstin") or extracted_data.get("gst_number")
    if gstin:
        gstin_str = str(gstin).strip()
        if not re.match(r"^\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z0-9]{2}$", gstin_str):
            flags.append(
                f"GSTIN_FORMAT_INVALID: '{gstin_str}' doesn't match standard "
                "15-character GSTIN format"
            )
        checks["gstin"] = gstin_str

    checks["flags"] = flags
    return checks
