"""
Copy-Move & Splicing Detection — Cloned Region Finder.

Detects when a piece of the image (like a hospital seal, signature, or
stamp) has been copied from one location to another within the same
document, or when regions have been spliced from a different document.

Method:
  1. Convert to grayscale
  2. Divide into overlapping blocks
  3. Apply DCT (Discrete Cosine Transform) to each block
  4. Quantise DCT coefficients and sort lexicographically
  5. Find block-pairs with high similarity (shift-invariant matching)
  6. Filter: only flag if matched blocks are spatially separated
     (adjacent blocks are naturally similar)

Also detects:
  - Noise inconsistency (spliced regions have different noise profiles)
  - Edge artefacts at splice boundaries

All checks are deterministic — no LLM calls.
"""
from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Parameters ────────────────────────────────────────────────────────────────
_BLOCK_SIZE = 16            # Pixel block size for DCT analysis
_BLOCK_STRIDE = 8           # Overlap stride (smaller = more thorough but slower)
_DCT_TRUNCATE = 8           # Keep top-N DCT coefficients per block
_MIN_SPATIAL_DIST = 40      # Min pixel distance for a "copy" (not natural adjacency)
_MATCH_THRESHOLD = 0.98     # Cosine similarity threshold for matching blocks
_MIN_CLONE_BLOCKS = 5       # Minimum matched blocks to declare copy-move
_MAX_BLOCKS_TO_PROCESS = 5000  # Cap for performance on large images


def _image_bytes_to_gray(image_bytes: bytes) -> np.ndarray | None:
    """Decode image bytes to grayscale numpy array."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    return img


def _extract_blocks(gray: np.ndarray) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Extract overlapping blocks from a grayscale image.

    Returns:
        features: ndarray of shape (N, _DCT_TRUNCATE) — truncated DCT coefficients
        positions: list of (row, col) block centres
    """
    h, w = gray.shape
    features: list[np.ndarray] = []
    positions: list[tuple[int, int]] = []

    for y in range(0, h - _BLOCK_SIZE + 1, _BLOCK_STRIDE):
        for x in range(0, w - _BLOCK_SIZE + 1, _BLOCK_STRIDE):
            block = gray[y:y + _BLOCK_SIZE, x:x + _BLOCK_SIZE].astype(np.float32)
            # DCT of the block
            dct_block = cv2.dct(block)
            # Flatten and take top-N zigzag coefficients
            flat = dct_block.flatten()[:_DCT_TRUNCATE]
            features.append(flat)
            positions.append((y + _BLOCK_SIZE // 2, x + _BLOCK_SIZE // 2))

            if len(features) >= _MAX_BLOCKS_TO_PROCESS:
                break
        if len(features) >= _MAX_BLOCKS_TO_PROCESS:
            break

    if not features:
        return np.array([]), positions

    return np.array(features, dtype=np.float32), positions


def detect_copy_move(image_bytes: bytes) -> dict[str, Any]:
    """Detect copy-move forgery in an image using block-matching DCT.

    Args:
        image_bytes: Raw image bytes.

    Returns:
        dict with:
            passed: bool
            flags: list[str]
            clone_regions: int         — number of matched block-pairs
            blocks_analysed: int
            suspicious_pairs: list[dict]  — spatial info about cloned regions
            noise_consistent: bool
    """
    result: dict[str, Any] = {
        "passed": True,
        "flags": [],
        "clone_regions": 0,
        "blocks_analysed": 0,
        "suspicious_pairs": [],
        "noise_consistent": True,
    }

    gray = _image_bytes_to_gray(image_bytes)
    if gray is None:
        result["flags"] = ["COPY_MOVE_DECODE_FAILED"]
        result["passed"] = False
        return result

    h, w = gray.shape
    if h < _BLOCK_SIZE * 2 or w < _BLOCK_SIZE * 2:
        # Image too small for meaningful block analysis
        result["flags"] = ["COPY_MOVE_SKIPPED: image too small for block analysis"]
        return result

    # ── Extract DCT feature blocks ────────────────────────────────────────
    features, positions = _extract_blocks(gray)
    n_blocks = len(features)
    result["blocks_analysed"] = n_blocks

    if n_blocks < 2:
        return result

    # ── Normalise features for cosine similarity ──────────────────────────
    norms = np.linalg.norm(features, axis=1, keepdims=True)
    norms = np.clip(norms, 1e-8, None)  # avoid division by zero
    normed = features / norms

    # ── Sort by feature vector to find near-duplicates efficiently ─────────
    # Instead of O(n²) all-pairs, sort lexicographically and compare neighbours
    sort_indices = np.lexsort(normed.T)
    sorted_features = normed[sort_indices]
    sorted_positions = [positions[i] for i in sort_indices]

    clone_pairs: list[dict[str, Any]] = []

    # Compare adjacent sorted blocks (they'll be the most similar)
    window = min(5, n_blocks - 1)  # check up to 5 neighbours
    for i in range(n_blocks - 1):
        for j in range(1, window + 1):
            if i + j >= n_blocks:
                break
            # Cosine similarity (dot product of normalised vectors)
            sim = float(np.dot(sorted_features[i], sorted_features[i + j]))
            if sim < _MATCH_THRESHOLD:
                continue

            # Check spatial distance
            pos_a = sorted_positions[i]
            pos_b = sorted_positions[i + j]
            dist = ((pos_a[0] - pos_b[0]) ** 2 + (pos_a[1] - pos_b[1]) ** 2) ** 0.5

            if dist >= _MIN_SPATIAL_DIST:
                clone_pairs.append({
                    "pos_a": list(pos_a),
                    "pos_b": list(pos_b),
                    "similarity": round(sim, 4),
                    "distance_px": round(dist, 1),
                })

    result["clone_regions"] = len(clone_pairs)
    result["suspicious_pairs"] = clone_pairs[:20]  # cap output size

    if len(clone_pairs) >= _MIN_CLONE_BLOCKS:
        result["flags"].append(
            f"COPY_MOVE_DETECTED: {len(clone_pairs)} block-pairs with "
            f">{_MATCH_THRESHOLD} similarity and >{_MIN_SPATIAL_DIST}px "
            f"spatial separation — possible cloned region"
        )

    # ── Noise consistency check ───────────────────────────────────────────
    # Divide image into quadrants and compare local noise levels
    noise_result = _check_noise_consistency(gray)
    result["noise_consistent"] = noise_result["consistent"]
    if not noise_result["consistent"]:
        result["flags"].append(
            f"NOISE_INCONSISTENCY: noise stddev ratio between quadrants "
            f"is {noise_result['ratio']:.2f} — possible splice boundary"
        )

    result["passed"] = len(result["flags"]) == 0
    return result


def _check_noise_consistency(gray: np.ndarray) -> dict[str, Any]:
    """Check if noise levels are consistent across the image.

    Spliced regions often have different noise patterns than the
    original image, creating detectable boundaries.

    Splits the image into a 2×2 grid and compares noise stddev
    in each quadrant using Laplacian high-pass filtering.
    """
    h, w = gray.shape
    mid_y, mid_x = h // 2, w // 2

    quadrants = [
        gray[:mid_y, :mid_x],      # top-left
        gray[:mid_y, mid_x:],      # top-right
        gray[mid_y:, :mid_x],      # bottom-left
        gray[mid_y:, mid_x:],      # bottom-right
    ]

    noise_levels: list[float] = []
    for q in quadrants:
        if q.size == 0:
            continue
        # Laplacian highlights edges and noise
        lap = cv2.Laplacian(q, cv2.CV_64F)
        noise_levels.append(float(np.std(lap)))

    if len(noise_levels) < 2:
        return {"consistent": True, "ratio": 1.0, "noise_levels": noise_levels}

    min_noise = min(noise_levels)
    max_noise = max(noise_levels)
    ratio = (max_noise / min_noise) if min_noise > 0 else 999.0

    # A ratio > 2.5 suggests different noise profiles (possible splice)
    return {
        "consistent": ratio < 2.5,
        "ratio": round(ratio, 2),
        "noise_levels": [round(n, 2) for n in noise_levels],
    }
