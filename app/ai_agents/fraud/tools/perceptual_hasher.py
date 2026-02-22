"""
Perceptual Hashing — Template Farm & Duplicate Detection.

Unlike a cryptographic hash (MD5/SHA) which changes entirely if a single
pixel moves, a **Perceptual Hash** (pHash) stays similar when the image
is resized, slightly recoloured, or re-compressed.

Fraudsters often reuse the same "fake" bill template for multiple claims,
changing only the name/amount.  By comparing perceptual hashes we detect:

  1. Near-duplicate documents (same template, minor edits)
  2. Screenshot-of-screen artifacts (digital camera pointed at monitor)
  3. Template farm patterns (bulk-produced bills)

We generate multiple hash types for robustness:
  - Average Hash  (aHash)  — fast, orientation-sensitive
  - Perceptual Hash (pHash) — DCT-based, rotation-resistant
  - Difference Hash (dHash) — gradient-based, scale-resistant

All checks are deterministic — no LLM calls.
"""
from __future__ import annotations

import io
import logging
from typing import Any

import imagehash
from PIL import Image

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
# Hamming distance thresholds (lower = more similar)
_NEAR_DUPLICATE_THRESHOLD = 8    # ≤8 bits different → near-duplicate
_SUSPICIOUS_THRESHOLD = 16       # ≤16 → suspicious similarity
_HASH_SIZE = 16                  # 16×16 hash → 256 bits of resolution


def compute_hashes(image_bytes: bytes) -> dict[str, Any]:
    """Compute perceptual hashes for a document image.

    Args:
        image_bytes: Raw image bytes.

    Returns:
        dict with keys:
            ahash: str     — average hash hex string
            phash: str     — perceptual hash hex string
            dhash: str     — difference hash hex string
            hash_size: int — the hash grid size used
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        logger.warning("Cannot open image for hashing: %s", exc)
        return {
            "ahash": None,
            "phash": None,
            "dhash": None,
            "hash_size": _HASH_SIZE,
            "error": str(exc),
        }

    return {
        "ahash": str(imagehash.average_hash(img, hash_size=_HASH_SIZE)),
        "phash": str(imagehash.phash(img, hash_size=_HASH_SIZE)),
        "dhash": str(imagehash.dhash(img, hash_size=_HASH_SIZE)),
        "hash_size": _HASH_SIZE,
    }


def compare_hashes(
    hash_a: dict[str, Any],
    hash_b: dict[str, Any],
    label_a: str = "doc_A",
    label_b: str = "doc_B",
) -> dict[str, Any]:
    """Compare two sets of perceptual hashes.

    Args:
        hash_a: Output of compute_hashes() for document A.
        hash_b: Output of compute_hashes() for document B.
        label_a: Human label for doc A.
        label_b: Human label for doc B.

    Returns:
        dict with:
            passed: bool
            flags: list[str]
            distances: {ahash: int, phash: int, dhash: int}
            verdict: DUPLICATE | NEAR_DUPLICATE | SUSPICIOUS | DISTINCT
    """
    result: dict[str, Any] = {
        "passed": True,
        "flags": [],
        "distances": {},
        "verdict": "DISTINCT",
        "label_a": label_a,
        "label_b": label_b,
    }

    distances: dict[str, int | None] = {}

    for hash_type in ("ahash", "phash", "dhash"):
        a_hex = hash_a.get(hash_type)
        b_hex = hash_b.get(hash_type)
        if a_hex is None or b_hex is None:
            distances[hash_type] = None
            continue
        try:
            a_hash = imagehash.hex_to_hash(a_hex)
            b_hash = imagehash.hex_to_hash(b_hex)
            distances[hash_type] = int(a_hash - b_hash)
        except Exception:
            distances[hash_type] = None

    result["distances"] = distances

    # Use pHash as the primary (most robust), with others as confirmation
    phash_dist = distances.get("phash")
    dhash_dist = distances.get("dhash")
    ahash_dist = distances.get("ahash")

    if phash_dist is None:
        return result  # can't compare

    flags: list[str] = []

    if phash_dist == 0:
        result["verdict"] = "DUPLICATE"
        flags.append(
            f"PHASH_DUPLICATE: {label_a} and {label_b} are perceptually "
            f"identical (pHash distance=0)"
        )
    elif phash_dist <= _NEAR_DUPLICATE_THRESHOLD:
        result["verdict"] = "NEAR_DUPLICATE"
        flags.append(
            f"PHASH_NEAR_DUPLICATE: {label_a} and {label_b} differ by only "
            f"{phash_dist} bits — likely same template with minor edits"
        )
    elif phash_dist <= _SUSPICIOUS_THRESHOLD:
        # Only flag as suspicious if dhash/ahash also close
        confirming = 0
        if dhash_dist is not None and dhash_dist <= _SUSPICIOUS_THRESHOLD:
            confirming += 1
        if ahash_dist is not None and ahash_dist <= _SUSPICIOUS_THRESHOLD:
            confirming += 1

        if confirming >= 1:
            result["verdict"] = "SUSPICIOUS"
            flags.append(
                f"PHASH_SUSPICIOUS: {label_a} and {label_b} have pHash "
                f"distance={phash_dist} with {confirming} confirming hash(es)"
            )

    result["flags"] = flags
    result["passed"] = result["verdict"] == "DISTINCT"

    return result


def detect_duplicates_in_set(
    hash_list: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare all pairs in a set of document hashes.

    Args:
        hash_list: List of {document_id, hashes: compute_hashes() output}

    Returns:
        dict with:
            passed: bool
            flags: list[str]
            comparisons: list[dict]
            duplicate_pairs: list[tuple[str, str]]
    """
    comparisons: list[dict[str, Any]] = []
    duplicate_pairs: list[tuple[str, str]] = []
    flags: list[str] = []

    for i in range(len(hash_list)):
        for j in range(i + 1, len(hash_list)):
            doc_a = hash_list[i]
            doc_b = hash_list[j]

            label_a = doc_a.get("document_id", f"doc_{i}")
            label_b = doc_b.get("document_id", f"doc_{j}")

            comparison = compare_hashes(
                doc_a.get("hashes", {}),
                doc_b.get("hashes", {}),
                label_a=label_a,
                label_b=label_b,
            )
            comparisons.append(comparison)

            if comparison["verdict"] in ("DUPLICATE", "NEAR_DUPLICATE"):
                duplicate_pairs.append((label_a, label_b))
                flags.extend(comparison["flags"])
            elif comparison["verdict"] == "SUSPICIOUS":
                flags.extend(comparison["flags"])

    return {
        "passed": len(duplicate_pairs) == 0,
        "flags": flags,
        "comparisons": comparisons,
        "duplicate_pairs": duplicate_pairs,
        "total_pairs_checked": len(comparisons),
    }
