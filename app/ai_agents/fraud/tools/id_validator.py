"""
Indian Government ID Validators — deterministic, no LLM.

PAN: Structural code validation (position-based character rules).
Aadhaar: Verhoeff checksum algorithm (the 12th digit is mathematically derived).

These catch Gemini hallucinations where the model "guesses" digits
to make an ID look valid.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PAN VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Format: ABCDE1234F  (5 letters, 4 digits, 1 letter)
#   Pos 1-3: alphabetic series (AAA–ZZZ)
#   Pos 4:   holder status — P=Individual, C=Company, H=HUF, F=Firm, etc.
#   Pos 5:   first letter of surname
#   Pos 6-9: four digits (0001–9999)
#   Pos 10:  check letter (alphabetic)

_PAN_REGEX = re.compile(r"^[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]$")

# Status codes at position 4
_PAN_STATUS_CODES = {
    "A": "Association of Persons (AOP)",
    "B": "Body of Individuals (BOI)",
    "C": "Company",
    "F": "Firm",
    "G": "Government",
    "H": "HUF (Hindu Undivided Family)",
    "L": "Local Authority",
    "J": "Artificial Juridical Person",
    "P": "Individual (Person)",
    "T": "Trust",
}


def validate_pan(pan: str, expect_individual: bool = True) -> dict[str, Any]:
    """Validate a PAN number structurally.

    Args:
        pan: The PAN string extracted by Gemini.
        expect_individual: If True, flag non-'P' status codes for insurance claims.

    Returns:
        {
            "valid": bool,
            "pan": str (cleaned),
            "status_code": str or None,
            "status_meaning": str or None,
            "flags": list[str],
            "detail": str,
        }
    """
    cleaned = re.sub(r"[\s\-]", "", str(pan).upper().strip())
    flags: list[str] = []

    if len(cleaned) != 10:
        return {
            "valid": False,
            "pan": cleaned,
            "status_code": None,
            "status_meaning": None,
            "flags": ["PAN_INVALID_LENGTH"],
            "detail": f"PAN must be 10 characters, got {len(cleaned)}",
        }

    if not _PAN_REGEX.match(cleaned):
        return {
            "valid": False,
            "pan": cleaned,
            "status_code": cleaned[3] if len(cleaned) > 3 else None,
            "status_meaning": None,
            "flags": ["PAN_INVALID_FORMAT"],
            "detail": f"PAN '{cleaned}' does not match format AAAAA0000A",
        }

    status_code = cleaned[3]
    status_meaning = _PAN_STATUS_CODES.get(status_code, f"Unknown ({status_code})")

    if expect_individual and status_code != "P":
        flags.append("PAN_NOT_INDIVIDUAL")
        detail = (
            f"PAN {cleaned}: position-4 is '{status_code}' ({status_meaning}), "
            f"expected 'P' (Individual) for personal insurance claim"
        )
    else:
        detail = f"PAN {cleaned}: valid format, status={status_meaning}"

    return {
        "valid": True,
        "pan": cleaned,
        "status_code": status_code,
        "status_meaning": status_meaning,
        "flags": flags,
        "detail": detail,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AADHAAR VALIDATION — Verhoeff Algorithm
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Verhoeff tables
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def _verhoeff_checksum(number: str) -> int:
    """Calculate the Verhoeff checksum digit for a numeric string."""
    c = 0
    for i, digit in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(digit)]]
    return c


def _verhoeff_validate(number: str) -> bool:
    """Validate a number string using the Verhoeff algorithm.

    The full number (including check digit) should produce checksum 0.
    """
    return _verhoeff_checksum(number) == 0


def validate_aadhaar(aadhaar: str) -> dict[str, Any]:
    """Validate an Aadhaar number using the Verhoeff algorithm.

    Args:
        aadhaar: The 12-digit Aadhaar string extracted by Gemini.

    Returns:
        {
            "valid": bool,
            "aadhaar_masked": str (last 4 only),
            "checksum_passed": bool,
            "is_masked": bool,
            "flags": list[str],
            "detail": str,
        }
    """
    cleaned = re.sub(r"[\s\-]", "", str(aadhaar).strip())

    # Detect masked Aadhaar (XXXX-XXXX-1234 pattern)
    has_mask = bool(re.search(r"[Xx*]{4,}", cleaned))
    digits_only = re.sub(r"[^0-9]", "", cleaned)

    if has_mask:
        return {
            "valid": True,
            "aadhaar_masked": f"XXXX-XXXX-{digits_only[-4:]}" if len(digits_only) >= 4 else cleaned,
            "checksum_passed": False,
            "is_masked": True,
            "flags": [],
            "detail": f"Aadhaar is masked (as expected). Last 4: {digits_only[-4:] if len(digits_only) >= 4 else '?'}",
        }

    if len(digits_only) != 12:
        return {
            "valid": False,
            "aadhaar_masked": f"XXXX-XXXX-{digits_only[-4:]}" if len(digits_only) >= 4 else cleaned,
            "checksum_passed": False,
            "is_masked": False,
            "flags": ["AADHAAR_INVALID_LENGTH"],
            "detail": f"Aadhaar must be 12 digits, got {len(digits_only)} digits from '{cleaned}'",
        }

    # Aadhaar cannot start with 0 or 1
    if digits_only[0] in ("0", "1"):
        return {
            "valid": False,
            "aadhaar_masked": f"XXXX-XXXX-{digits_only[-4:]}",
            "checksum_passed": False,
            "is_masked": False,
            "flags": ["AADHAAR_INVALID_START"],
            "detail": f"Aadhaar cannot start with {digits_only[0]}",
        }

    # Run Verhoeff checksum
    checksum_ok = _verhoeff_validate(digits_only)

    flags: list[str] = []
    if not checksum_ok:
        flags.append("AADHAAR_CHECKSUM_FAIL")

    return {
        "valid": checksum_ok,
        "aadhaar_masked": f"XXXX-XXXX-{digits_only[-4:]}",
        "checksum_passed": checksum_ok,
        "is_masked": False,
        "flags": flags,
        "detail": (
            f"Aadhaar XXXX-XXXX-{digits_only[-4:]}: Verhoeff checksum {'PASSED' if checksum_ok else 'FAILED'}"
        ),
    }
