"""PII sanitizer — strips personally identifiable fields before storing feature snapshots."""
from __future__ import annotations

from typing import Any

_STRICT_PII_KEYS = {
    "patient_name", "name", "full_name", "email", "phone", "address",
    "aadhaar", "pan", "passport", "dob", "date_of_birth", "ip_address",
}

_PARTIAL_PII_KEYS = {
    "provider_id", "hospital_id", "claimant_id",
}


def sanitize(context: dict[str, Any], mode: str = "strict") -> dict[str, Any]:
    """
    Return a copy of context with PII removed.
    - strict: removes all _STRICT_PII_KEYS and any UUID-like user identifiers
    - partial: removes _STRICT_PII_KEYS, keeps provider IDs for network analysis
    """
    result = {}
    for k, v in context.items():
        key_lower = k.lower()
        if any(pii in key_lower for pii in _STRICT_PII_KEYS):
            result[k] = "[REDACTED]"
        elif mode == "strict" and any(p in key_lower for p in _PARTIAL_PII_KEYS):
            result[k] = "[REDACTED]"
        elif isinstance(v, dict):
            result[k] = sanitize(v, mode)
        else:
            result[k] = v
    return result
