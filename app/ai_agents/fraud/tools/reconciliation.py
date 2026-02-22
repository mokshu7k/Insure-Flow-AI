"""
Three-Way Reconciliation Engine — the heart of Extraction Integrity.

Cross-references three independent sources:
  1. Raw PDF text stream (PyMuPDF)
  2. Primary Gemini extraction (full JSON)
  3. Shadow Gemini extraction (just the total)

Plus optional coordinate verification (visual anchor check).

Outputs an integrity_risk_score (0–100) and detailed per-check results.
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.ai_agents.fraud.tools.pdf_extractor import normalize_number_string

logger = logging.getLogger(__name__)

# ── Risk weights per check ────────────────────────────────────────────────────
RISK_WEIGHTS = {
    "literal_match":       80,   # Value in JSON not found in raw text
    "math_mismatch":      100,   # Σ line_items ≠ extracted total
    "shadow_discrepancy":  40,   # Primary total ≠ Shadow total
    "coordinate_check":   100,   # Cropped image text ≠ extracted text
}


def _to_decimal(value: Any) -> Decimal | None:
    """Safely convert a value to Decimal."""
    if value is None:
        return None
    try:
        s = str(value).replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _fuzzy_find_in_text(value: Any, raw_text: str) -> bool:
    """Check if a value (number or string) appears in the raw text stream.

    For numbers: tries multiple formats (with/without commas, decimals).
    For strings: does case-insensitive substring search.
    """
    if value is None:
        return True  # Can't verify null — assume OK

    raw_lower = raw_text.lower()

    # For numbers, try multiple normalizations
    if isinstance(value, (int, float, Decimal)):
        norm = normalize_number_string(value)
        if norm in raw_text.replace(",", "").replace(" ", ""):
            return True

        # Try with Indian comma format (1,45,000)
        try:
            int_val = int(Decimal(str(value)))
            # Indian format: last 3 digits, then groups of 2
            s = str(int_val)
            if len(s) > 3:
                indian = s[-3:]
                remaining = s[:-3]
                while remaining:
                    indian = remaining[-2:] + "," + indian
                    remaining = remaining[:-2]
                if indian in raw_text:
                    return True
            # Western format
            western = f"{int_val:,}"
            if western in raw_text:
                return True
        except (ValueError, InvalidOperation):
            pass

        return False

    # For strings, fuzzy case-insensitive search
    str_val = str(value).strip().lower()
    if len(str_val) < 2:
        return True  # Too short to verify meaningfully
    return str_val in raw_lower


def literal_anchor_check(
    extracted_data: dict[str, Any],
    raw_text: str,
) -> dict[str, Any]:
    """Check 1: Verify every extracted field exists in the raw PDF text stream.

    Returns:
        {
            "passed": bool,
            "total_fields": int,
            "matched_fields": int,
            "mismatched_fields": [{"key": ..., "extracted_value": ..., "found_in_raw": False}],
            "match_rate": float (0.0 – 1.0),
        }
    """
    # Fields worth checking (skip internal/meta keys)
    skip_keys = {"_extraction_notes", "_wrong_document_type", "_detected_type",
                 "_parse_error", "line_items"}

    results: list[dict[str, Any]] = []
    matched = 0
    total = 0

    for key, value in extracted_data.items():
        if key in skip_keys or value is None:
            continue

        total += 1
        found = _fuzzy_find_in_text(value, raw_text)
        results.append({
            "key": key,
            "extracted_value": str(value)[:100],
            "found_in_raw": found,
        })
        if found:
            matched += 1

    # Also check individual line item amounts
    line_items = extracted_data.get("line_items", [])
    for i, item in enumerate(line_items):
        amount = item.get("amount")
        if amount is not None:
            total += 1
            found = _fuzzy_find_in_text(amount, raw_text)
            results.append({
                "key": f"line_items[{i}].amount",
                "extracted_value": str(amount),
                "found_in_raw": found,
            })
            if found:
                matched += 1

    match_rate = matched / total if total > 0 else 1.0
    mismatched = [r for r in results if not r["found_in_raw"]]

    return {
        "passed": len(mismatched) == 0,
        "total_fields": total,
        "matched_fields": matched,
        "mismatched_fields": mismatched,
        "match_rate": match_rate,
    }


def arithmetic_recalculation(
    extracted_data: dict[str, Any],
) -> dict[str, Any]:
    """Check 2: Sum line_items using Python's Decimal and compare to extracted total.

    Returns:
        {
            "passed": bool,
            "calculated_sum": str (Decimal),
            "extracted_total": str (Decimal) or None,
            "difference": str (Decimal),
            "difference_pct": float,
            "line_item_count": int,
        }
    """
    line_items = extracted_data.get("line_items", [])
    extracted_total_raw = extracted_data.get("total_amount")

    # Sum all line item amounts using Decimal
    calculated_sum = Decimal("0")
    valid_items = 0
    for item in line_items:
        amount = _to_decimal(item.get("amount"))
        if amount is not None:
            calculated_sum += amount
            valid_items += 1

    extracted_total = _to_decimal(extracted_total_raw)

    if extracted_total is None or valid_items == 0:
        return {
            "passed": True,  # Can't verify — not a failure
            "calculated_sum": str(calculated_sum),
            "extracted_total": str(extracted_total) if extracted_total else None,
            "difference": "0",
            "difference_pct": 0.0,
            "line_item_count": valid_items,
            "skipped": True,
            "skip_reason": "missing_total" if extracted_total is None else "no_line_items",
        }

    difference = abs(calculated_sum - extracted_total)
    # Allow small tolerance (rounding errors)
    tolerance = max(Decimal("1.00"), extracted_total * Decimal("0.01"))  # 1% or ₹1

    passed = difference <= tolerance
    diff_pct = float(difference / extracted_total * 100) if extracted_total > 0 else 0.0

    return {
        "passed": passed,
        "calculated_sum": str(calculated_sum),
        "extracted_total": str(extracted_total),
        "difference": str(difference),
        "difference_pct": round(diff_pct, 2),
        "line_item_count": valid_items,
    }


def shadow_comparison(
    primary_total_raw: Any,
    shadow_total: float | None,
) -> dict[str, Any]:
    """Check 3: Compare primary extraction total vs shadow extraction total.

    Returns:
        {
            "passed": bool,
            "primary_total": float or None,
            "shadow_total": float or None,
            "difference": float,
            "difference_pct": float,
        }
    """
    primary = _to_decimal(primary_total_raw)
    shadow = Decimal(str(shadow_total)) if shadow_total is not None else None

    if primary is None or shadow is None:
        return {
            "passed": True,  # Can't compare — not a failure
            "primary_total": float(primary) if primary else None,
            "shadow_total": float(shadow) if shadow else None,
            "difference": 0.0,
            "difference_pct": 0.0,
            "skipped": True,
            "skip_reason": "missing_primary" if primary is None else "missing_shadow",
        }

    difference = abs(primary - shadow)
    # Allow 2% tolerance for rounding / formatting differences
    tolerance = max(Decimal("1.00"), primary * Decimal("0.02"))

    passed = difference <= tolerance
    diff_pct = float(difference / primary * 100) if primary > 0 else 0.0

    return {
        "passed": passed,
        "primary_total": float(primary),
        "shadow_total": float(shadow),
        "difference": float(difference),
        "difference_pct": round(diff_pct, 2),
    }


def coordinate_verification(
    coordinate_data: dict[str, Any] | None,
    primary_total_raw: Any,
    page_images: list[bytes] | None = None,
) -> dict[str, Any]:
    """Check 4: Verify the visual anchor — does the total at the coordinates
    match what the primary extraction reported?

    If Tesseract is available, crops the bounding box and OCRs it.
    Otherwise, compares Gemini's coordinate-call value vs primary total.

    Returns:
        {
            "passed": bool,
            "coordinate_value": str,
            "primary_value": str,
            "method": "gemini_coordinate" | "tesseract_crop" | "skipped",
        }
    """
    if coordinate_data is None:
        return {
            "passed": True,
            "coordinate_value": None,
            "primary_value": str(primary_total_raw),
            "method": "skipped",
            "skip_reason": "no_coordinate_data",
        }

    coord_value_str = str(coordinate_data.get("value", ""))
    primary_norm = normalize_number_string(primary_total_raw)
    coord_norm = normalize_number_string(coord_value_str)

    # If Tesseract is available AND we have images + bounding box, crop & OCR
    tesseract_value = None
    bbox = coordinate_data.get("bounding_box")
    if page_images and bbox and len(bbox) == 4:
        try:
            import pytesseract
            from PIL import Image
            import io

            # Load first page image
            img = Image.open(io.BytesIO(page_images[0]))
            img_w, img_h = img.size

            # Gemini returns coordinates normalized to 0-1000
            ymin, xmin, ymax, xmax = bbox
            # Convert to pixel coordinates
            left = int(xmin / 1000 * img_w)
            top = int(ymin / 1000 * img_h)
            right = int(xmax / 1000 * img_w)
            bottom = int(ymax / 1000 * img_h)

            # Add some padding
            pad = 10
            left = max(0, left - pad)
            top = max(0, top - pad)
            right = min(img_w, right + pad)
            bottom = min(img_h, bottom + pad)

            crop = img.crop((left, top, right, bottom))
            tesseract_text = pytesseract.image_to_string(crop, config="--psm 7").strip()
            tesseract_value = normalize_number_string(tesseract_text)
            logger.info("Tesseract OCR on crop: '%s' → normalized: '%s'", tesseract_text, tesseract_value)

        except ImportError:
            logger.info("Tesseract not available, using Gemini coordinate value only")
        except Exception as exc:
            logger.warning("Tesseract crop failed: %s", exc)

    if tesseract_value is not None:
        passed = tesseract_value == primary_norm or tesseract_value == coord_norm
        return {
            "passed": passed,
            "coordinate_value": coord_value_str,
            "tesseract_value": tesseract_value,
            "primary_value": str(primary_total_raw),
            "method": "tesseract_crop",
        }

    # Fall back to comparing Gemini's coordinate value vs primary total
    passed = coord_norm == primary_norm
    return {
        "passed": passed,
        "coordinate_value": coord_value_str,
        "primary_value": str(primary_total_raw),
        "method": "gemini_coordinate",
    }


def calculate_integrity_score(check_results: dict[str, dict[str, Any]]) -> tuple[float, list[str]]:
    """Calculate the composite integrity risk score (0–100) from individual checks.

    Returns:
        (score, flags) where score is 0–100 and flags are human-readable strings.
    """
    weighted_penalties: list[float] = []
    flags: list[str] = []

    # 1. Literal match check
    literal = check_results.get("literal_match", {})
    if not literal.get("passed", True) and not literal.get("skipped"):
        match_rate = literal.get("match_rate", 1.0)
        # Penalty scales with mismatch rate
        penalty = RISK_WEIGHTS["literal_match"] * (1.0 - match_rate)
        weighted_penalties.append(penalty)
        mismatched = literal.get("mismatched_fields", [])
        mismatch_keys = [m["key"] for m in mismatched[:3]]
        flags.append(f"RAW_TEXT_MISMATCH: {', '.join(mismatch_keys)} not found in PDF text stream")

    # 2. Arithmetic recalculation
    arith = check_results.get("arithmetic", {})
    if not arith.get("passed", True) and not arith.get("skipped"):
        diff_pct = arith.get("difference_pct", 0)
        # Full penalty above 5% difference, scaled below
        severity = min(1.0, diff_pct / 5.0)
        penalty = RISK_WEIGHTS["math_mismatch"] * severity
        weighted_penalties.append(penalty)
        flags.append(
            f"MATH_MISMATCH: line_items sum={arith.get('calculated_sum')} "
            f"vs total={arith.get('extracted_total')} (diff {diff_pct:.1f}%)"
        )

    # 3. Shadow discrepancy
    shadow = check_results.get("shadow", {})
    if not shadow.get("passed", True) and not shadow.get("skipped"):
        diff_pct = shadow.get("difference_pct", 0)
        severity = min(1.0, diff_pct / 10.0)
        penalty = RISK_WEIGHTS["shadow_discrepancy"] * severity
        weighted_penalties.append(penalty)
        flags.append(
            f"SHADOW_DISCREPANCY: primary_total={shadow.get('primary_total')} "
            f"vs shadow_total={shadow.get('shadow_total')} (diff {diff_pct:.1f}%)"
        )

    # 4. Coordinate check
    coord = check_results.get("coordinate", {})
    if not coord.get("passed", True) and coord.get("method") != "skipped":
        weighted_penalties.append(RISK_WEIGHTS["coordinate_check"])
        flags.append(
            f"COORDINATE_MISMATCH: visual='{coord.get('coordinate_value')}' "
            f"vs extracted='{coord.get('primary_value')}'"
        )

    # Composite score: highest single penalty drives the score,
    # with additional penalties adding up to 20% more
    if not weighted_penalties:
        return 0.0, []

    max_penalty = max(weighted_penalties)
    others_sum = sum(p for p in weighted_penalties if p != max_penalty)
    # Cap the additional contribution at 20 points
    additional = min(20.0, others_sum * 0.25)
    score = min(100.0, max_penalty + additional)

    return round(score, 1), flags
