"""
Privacy Module
PII sanitisation gateway – every AI-bound payload MUST pass through here.
"""
from __future__ import annotations

import logging
import re
from copy import deepcopy
from typing import Any, Dict

from app.ai_agents.fraud import config as fraud_config

logger = logging.getLogger(__name__)

# Pre-compiled patterns
_PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "phone": re.compile(r"\b\d{10,13}\b"),
    "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
}

_VALID_MODES = ("strict", "balanced", "raw")


def sanitize(
    data: Dict[str, Any],
    mode: str | None = None,
) -> Dict[str, Any]:
    """
    Sanitise claim context for downstream AI processing.

    Args:
        data: Raw claim context dict.
        mode: Privacy mode override. Falls back to config default.
              Must be one of: strict, balanced, raw.
              **raw** requires explicit opt-in – never the default.

    Returns:
        Deep-copied sanitised dict (original untouched).

    Raises:
        ValueError: If an invalid mode is supplied.
    """
    effective_mode = mode or fraud_config.DEFAULT_PRIVACY_MODE

    if effective_mode not in _VALID_MODES:
        raise ValueError(
            f"Invalid privacy mode '{effective_mode}'. "
            f"Must be one of {_VALID_MODES}"
        )

    # raw mode is never the default – guard against misconfiguration
    if effective_mode == "raw" and mode is None:
        logger.warning(
            "Privacy mode resolved to 'raw' from config default – "
            "overriding to 'balanced' for safety."
        )
        effective_mode = "balanced"

    sanitized = deepcopy(data)

    if effective_mode == "raw":
        return sanitized

    if effective_mode == "strict":
        return _apply_strict(sanitized)

    # balanced
    return _apply_balanced(sanitized)


def _apply_strict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove all PII. Replace identifiable fields with placeholders."""
    _remove_keys(data, {"user_id", "policy_number", "user_name", "email", "phone"})

    amount = data.get("claim_amount")
    if amount is not None:
        data["claim_amount_band"] = _amount_to_band(amount)
        del data["claim_amount"]

    _scrub_string_values(data)
    return data


def _apply_balanced(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mask partial PII – keep amounts, mask policy number."""
    _remove_keys(data, {"user_name", "email", "phone"})

    policy = data.get("policy_number", "")
    if policy:
        data["policy_number"] = _mask_string(policy, visible_tail=4)

    if "user_id" in data:
        uid = str(data["user_id"])
        data["user_id"] = _mask_string(uid, visible_tail=4)

    _scrub_string_values(data)
    return data


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _remove_keys(data: Dict[str, Any], keys: set[str]) -> None:
    for key in keys:
        data.pop(key, None)


def _mask_string(value: str, visible_tail: int = 4) -> str:
    if len(value) <= visible_tail:
        return "*" * len(value)
    return "*" * (len(value) - visible_tail) + value[-visible_tail:]


def _amount_to_band(amount: float) -> str:
    if amount < 10_000:
        return "BELOW_10K"
    if amount < 50_000:
        return "10K_TO_50K"
    if amount < 100_000:
        return "50K_TO_100K"
    if amount < 500_000:
        return "100K_TO_500K"
    return "ABOVE_500K"


def _scrub_string_values(data: Dict[str, Any]) -> None:
    """Remove PII patterns from any remaining string values."""
    for key, value in list(data.items()):
        if isinstance(value, str):
            for _name, pattern in _PII_PATTERNS.items():
                value = pattern.sub("[REDACTED]", value)
            data[key] = value
