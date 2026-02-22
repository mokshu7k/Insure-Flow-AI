"""
Fuzzy and strict name/entity matching — deterministic, no LLM.

Uses thefuzz (Levenshtein distance) to compare names extracted from
different documents.  Gemini "normalises" names (R.K. Sharma → Rajesh
Kumar Sharma), which can hide fraud signals.  This tool catches that.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from thefuzz import fuzz

logger = logging.getLogger(__name__)

# ── Title / honorific prefixes common in Indian documents ─────────────────────
_TITLES = re.compile(
    r"^(mr\.?|mrs\.?|ms\.?|dr\.?|shri\.?|smt\.?|sri\.?|kumari?\.?|master\.?)\s+",
    re.IGNORECASE,
)


def _normalise(name: str) -> str:
    """Lowercase, strip titles, collapse whitespace."""
    name = name.strip().lower()
    name = _TITLES.sub("", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def strict_match(a: str, b: str) -> bool:
    """Exact equality after normalisation."""
    return _normalise(a) == _normalise(b)


def fuzzy_score(a: str, b: str) -> float:
    """Return 0.0–1.0 similarity using token-sort ratio.

    token_sort_ratio handles word-order differences:
       "Kumar Rajesh" vs "Rajesh Kumar" → 100
    """
    na, nb = _normalise(a), _normalise(b)
    if not na or not nb:
        return 0.0
    return fuzz.token_sort_ratio(na, nb) / 100.0


def compare_names(
    name_a: str,
    name_b: str,
    doc_a_label: str = "Doc A",
    doc_b_label: str = "Doc B",
    strict_threshold: float = 0.98,
    warn_threshold: float = 0.80,
    alert_threshold: float = 0.55,
) -> dict[str, Any]:
    """Compare two entity names with strict + fuzzy checks.

    Returns:
        {
            "name_a": str, "name_b": str,
            "strict_match": bool,
            "fuzzy_score": float (0–1),
            "verdict": "MATCH" | "MINOR_WARNING" | "IDENTITY_MISMATCH",
            "risk_weight": 0 | 20 | 80,
            "detail": str,
        }
    """
    s = strict_match(name_a, name_b)
    f = fuzzy_score(name_a, name_b)

    if s or f >= strict_threshold:
        verdict = "MATCH"
        risk_weight = 0
        detail = f"{doc_a_label} ↔ {doc_b_label}: exact/near-exact match"
    elif f >= warn_threshold:
        verdict = "MINOR_WARNING"
        risk_weight = 20
        detail = (
            f"{doc_a_label} '{name_a}' ↔ {doc_b_label} '{name_b}': "
            f"fuzzy={f:.2f} — possible abbreviation/spelling variant"
        )
    elif f >= alert_threshold:
        verdict = "IDENTITY_MISMATCH"
        risk_weight = 80
        detail = (
            f"{doc_a_label} '{name_a}' ↔ {doc_b_label} '{name_b}': "
            f"fuzzy={f:.2f} — likely different person"
        )
    else:
        verdict = "IDENTITY_MISMATCH"
        risk_weight = 100
        detail = (
            f"{doc_a_label} '{name_a}' ↔ {doc_b_label} '{name_b}': "
            f"fuzzy={f:.2f} — names do not match at all"
        )

    return {
        "name_a": name_a,
        "name_b": name_b,
        "doc_a": doc_a_label,
        "doc_b": doc_b_label,
        "strict_match": s,
        "fuzzy_score": round(f, 4),
        "verdict": verdict,
        "risk_weight": risk_weight,
        "detail": detail,
    }


def compare_dates_exact(
    date_a: Any,
    date_b: Any,
    label_a: str = "Doc A",
    label_b: str = "Doc B",
) -> dict[str, Any]:
    """Compare two date strings / date objects for exact equality.

    Handles DD/MM/YYYY, YYYY-MM-DD, and Python date objects.
    """
    from datetime import date, datetime

    def _to_date(v: Any):
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

    da = _to_date(date_a)
    db = _to_date(date_b)

    if da is None or db is None:
        return {
            "date_a": str(date_a), "date_b": str(date_b),
            "match": True, "skipped": True,
            "skip_reason": "unparseable_date",
            "detail": f"Cannot parse date(s): {label_a}='{date_a}', {label_b}='{date_b}'",
        }

    match = da == db
    return {
        "date_a": str(da), "date_b": str(db),
        "label_a": label_a, "label_b": label_b,
        "match": match,
        "diff_days": abs((da - db).days) if not match else 0,
        "detail": (
            f"{label_a} ({da}) == {label_b} ({db})" if match
            else f"DATE MISMATCH: {label_a} ({da}) ≠ {label_b} ({db}), diff={abs((da - db).days)}d"
        ),
    }
