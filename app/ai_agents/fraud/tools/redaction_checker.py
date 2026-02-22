"""
Redaction Integrity & Semantic-to-Raw Matcher — deterministic, no LLM.

Three-part tool:
1. **Redaction Integrity**: Detects when Gemini "sees through" masked IDs
   (compliance violation) or hallucinates digits (fraud).
2. **Semantic-to-Raw Matcher** ("Greedy String Matcher"): Verifies that
   every key field Gemini extracted actually exists character-for-character
   in the raw PDF text — catches cross-pollination / hallucination.
3. **ID Digit Completeness**: If Gemini outputs more digits than the raw
   text contains, something is wrong.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Masking patterns common in Indian documents ──────────────────────────────
_MASK_PATTERNS = [
    re.compile(r"[Xx*]{4,}"),  # XXXX or ****
    re.compile(r"[Xx*]{2,}\s*[-–]\s*[Xx*]{2,}"),  # XX-XX
]

# Fields that are sensitive and should be checked for redaction bypass
_SENSITIVE_FIELDS = {
    "aadhaar_number", "pan_number", "account_number", "ifsc_code",
    "bank_account", "mobile_number", "phone_number", "email",
}

# Fields to verify in the greedy matcher
_MATCHABLE_FIELDS = {
    "patient_name", "hospital_name", "doctor_name", "full_name",
    "treating_doctor_name", "lab_name", "pharmacy_name",
    "diagnosis", "primary_diagnosis", "bill_number", "fir_number",
    "hospital_gstin", "hospital_registration_no", "pharmacy_gstin",
    "deceased_name",
}


def _count_digits(s: str) -> int:
    """Count numeric digits in a string."""
    return sum(c.isdigit() for c in s)


def _is_masked(text: str) -> bool:
    """Check if a string looks like a masked/redacted value."""
    return any(p.search(text) for p in _MASK_PATTERNS)


def check_redaction_integrity(
    extracted_data: dict[str, Any],
    raw_text: str,
) -> dict[str, Any]:
    """Detect when Gemini bypasses document redactions or hallucinates digits.

    For each sensitive field:
    1. Find the corresponding text in raw_text
    2. If raw has fewer digits than Gemini's output → alarm (hallucination / bypass)
    3. If raw shows masking patterns but Gemini returned full digits → privacy alarm

    Returns:
        {
            "passed": bool,
            "checks": [
                {
                    "field": str,
                    "gemini_value": str,
                    "raw_digits": int,
                    "gemini_digits": int,
                    "raw_is_masked": bool,
                    "verdict": "CLEAN" | "PRIVACY_VIOLATION" | "HALLUCINATED_DIGITS",
                    "detail": str,
                }
            ],
            "privacy_violations": list[str],
            "hallucinated_fields": list[str],
        }
    """
    checks: list[dict[str, Any]] = []
    privacy_violations: list[str] = []
    hallucinated_fields: list[str] = []

    raw_lower = raw_text.lower()

    for field in _SENSITIVE_FIELDS:
        gemini_val = extracted_data.get(field)
        if gemini_val is None:
            continue

        gemini_str = str(gemini_val).strip()
        gemini_digits = _count_digits(gemini_str)

        if gemini_digits == 0:
            continue  # Nothing numeric to verify

        # Search raw text for this field's value or nearby masked patterns
        # Look for the last N digits of the Gemini value in raw text
        raw_masked = False
        raw_digit_count = 0

        # Strategy: find any nearby occurrence of the last 4 digits
        last_4 = re.sub(r"[^0-9]", "", gemini_str)[-4:] if gemini_digits >= 4 else ""

        if last_4 and last_4 in raw_text:
            # Found reference point — check surrounding area for masking
            idx = raw_text.index(last_4)
            # Look at 50 chars before
            context_start = max(0, idx - 50)
            context = raw_text[context_start:idx + len(last_4) + 10]
            raw_masked = _is_masked(context)
            raw_digit_count = _count_digits(context)
        else:
            # Can't find reference — check entire raw text for mask patterns near field names
            for pattern in [field.replace("_", " "), field.replace("_", "")]:
                if pattern in raw_lower:
                    pidx = raw_lower.index(pattern)
                    context = raw_text[pidx:pidx + 80]
                    raw_masked = _is_masked(context)
                    raw_digit_count = _count_digits(context)
                    break

        # Verdict
        if raw_masked and gemini_digits > raw_digit_count:
            verdict = "PRIVACY_VIOLATION"
            detail = (
                f"Gemini extracted {gemini_digits} digits for '{field}' but raw text "
                f"shows masking ({raw_digit_count} visible digits). "
                f"Model may have bypassed redaction — delete this data immediately."
            )
            privacy_violations.append(field)
        elif not raw_masked and gemini_digits > raw_digit_count + 2:
            verdict = "HALLUCINATED_DIGITS"
            detail = (
                f"Gemini extracted {gemini_digits} digits for '{field}' but raw text "
                f"only has {raw_digit_count} digits nearby. Possible hallucination."
            )
            hallucinated_fields.append(field)
        else:
            verdict = "CLEAN"
            detail = f"'{field}': {gemini_digits} digits, consistent with raw text"

        checks.append({
            "field": field,
            "gemini_value": gemini_str[:4] + "..." if len(gemini_str) > 8 else gemini_str,
            "raw_digits": raw_digit_count,
            "gemini_digits": gemini_digits,
            "raw_is_masked": raw_masked,
            "verdict": verdict,
            "detail": detail,
        })

    return {
        "passed": len(privacy_violations) == 0 and len(hallucinated_fields) == 0,
        "checks": checks,
        "privacy_violations": privacy_violations,
        "hallucinated_fields": hallucinated_fields,
    }


def greedy_string_matcher(
    extracted_data: dict[str, Any],
    raw_text: str,
) -> dict[str, Any]:
    """Verify that Gemini's extracted text fields exist literally in the raw PDF.

    The "Greedy String Matcher" ensures Gemini is a *recorder*, not an *editor*.
    If the extraction is "cleaner" than the document, Gemini is helping too much.

    Returns:
        {
            "passed": bool,
            "total_checked": int,
            "found_count": int,
            "not_found": [{"field": str, "gemini_value": str, "verdict": str}],
            "match_rate": float,
        }
    """
    raw_lower = raw_text.lower().strip()
    raw_words = set(raw_lower.split())

    results: list[dict[str, Any]] = []
    found = 0
    total = 0

    for field in _MATCHABLE_FIELDS:
        gemini_val = extracted_data.get(field)
        if gemini_val is None:
            continue

        gemini_str = str(gemini_val).strip()
        if len(gemini_str) < 2:
            continue

        total += 1
        gemini_lower = gemini_str.lower()

        # Check: exact substring match
        if gemini_lower in raw_lower:
            found += 1
            continue

        # Check: all individual words present (handles line breaks / whitespace)
        words = gemini_lower.split()
        all_words_found = all(w in raw_lower for w in words if len(w) > 1)
        if all_words_found:
            found += 1
            continue

        # NOT found — this is a signal
        results.append({
            "field": field,
            "gemini_value": gemini_str,
            "verdict": "NOT_FOUND_IN_RAW",
            "detail": (
                f"Gemini says '{field}' = '{gemini_str}' but this exact text "
                f"is NOT in the raw PDF. Possible hallucination or cross-pollination."
            ),
        })

    match_rate = found / total if total > 0 else 1.0

    return {
        "passed": len(results) == 0,
        "total_checked": total,
        "found_count": found,
        "not_found": results,
        "match_rate": round(match_rate, 4),
    }
