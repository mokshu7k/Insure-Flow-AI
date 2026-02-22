"""
Error Level Analysis (ELA) — Compression Artifact Detection.

When an image is modified (e.g., changing a "1" to a "9" in a bill),
the modified section has a different JPEG compression level than the
surrounding pixels.

Method:
  1. Re-save the image at a known quality (e.g., 95%)
  2. Compute the absolute pixel-wise difference between original
     and re-compressed image
  3. In a legitimate document, the ELA "heat" should be uniform.
     If a specific region glows brighter, it's been manually edited.

We also compute basic statistics:
  - Mean / StdDev of the ELA map
  - Max-hotspot intensity vs global mean ratio
  - Percentage of "hot" pixels (above threshold)
  - Structural Similarity Index (SSIM) between original and recompressed

All checks are deterministic — no LLM calls.
"""
from __future__ import annotations

import io
import logging
from typing import Any

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ── ELA parameters ────────────────────────────────────────────────────────────
_ELA_QUALITY = 95          # JPEG re-compression quality
_HOTSPOT_THRESHOLD = 50    # Pixel-level ELA value to be "hot"
_HOT_RATIO_ALERT = 3.0    # Hotspot mean / global mean ratio → flag
_HOT_PERCENTAGE_ALERT = 5.0  # % of hot pixels → flag
_SCALE_FACTOR = 15         # Amplification for ELA visualisation


def _image_bytes_to_cv2(image_bytes: bytes) -> np.ndarray | None:
    """Decode raw image bytes into an OpenCV BGR array."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _recompress_jpeg(image_bytes: bytes, quality: int = _ELA_QUALITY) -> bytes:
    """Re-save the image as JPEG at a known quality level."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def compute_ela(image_bytes: bytes, quality: int = _ELA_QUALITY) -> dict[str, Any]:
    """Perform Error Level Analysis on an image.

    Args:
        image_bytes: Raw image bytes (any format Pillow can open).
        quality: JPEG re-compression quality (default 95).

    Returns:
        dict with keys:
            passed: bool
            flags: list[str]
            ela_mean: float           — global mean of ELA map
            ela_stddev: float         — global stddev
            ela_max: float            — maximum pixel in ELA map
            hot_pixel_pct: float      — % of pixels above threshold
            hotspot_ratio: float      — max-region mean / global mean
            ssim: float               — Structural Similarity Index
            ela_map_shape: list[int]  — [H, W] of the ELA map
    """
    result: dict[str, Any] = {
        "passed": True,
        "flags": [],
        "ela_mean": 0.0,
        "ela_stddev": 0.0,
        "ela_max": 0.0,
        "hot_pixel_pct": 0.0,
        "hotspot_ratio": 0.0,
        "ssim": 1.0,
        "ela_map_shape": [0, 0],
    }

    try:
        # Decode original
        original = _image_bytes_to_cv2(image_bytes)
        if original is None:
            result["flags"] = ["ELA_DECODE_FAILED: cannot decode image"]
            result["passed"] = False
            return result

        # Re-compress and decode
        recompressed_bytes = _recompress_jpeg(image_bytes, quality)
        recompressed = _image_bytes_to_cv2(recompressed_bytes)
        if recompressed is None:
            result["flags"] = ["ELA_RECOMPRESS_FAILED"]
            result["passed"] = False
            return result

        # Resize to match (in case of rounding differences)
        if original.shape != recompressed.shape:
            recompressed = cv2.resize(
                recompressed, (original.shape[1], original.shape[0])
            )

        # ── Compute ELA map (absolute difference, amplified) ──────────────
        diff = cv2.absdiff(original, recompressed)
        ela_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        ela_amplified = np.clip(ela_gray.astype(np.float32) * _SCALE_FACTOR, 0, 255)

        result["ela_map_shape"] = list(ela_gray.shape[:2])

        # ── Global statistics ─────────────────────────────────────────────
        ela_mean = float(np.mean(ela_amplified))
        ela_stddev = float(np.std(ela_amplified))
        ela_max = float(np.max(ela_amplified))

        result["ela_mean"] = round(ela_mean, 2)
        result["ela_stddev"] = round(ela_stddev, 2)
        result["ela_max"] = round(ela_max, 2)

        # ── Hot pixel analysis ────────────────────────────────────────────
        hot_mask = ela_amplified > _HOTSPOT_THRESHOLD
        total_pixels = ela_amplified.size
        hot_count = int(np.sum(hot_mask))
        hot_pct = (hot_count / total_pixels * 100) if total_pixels > 0 else 0.0
        result["hot_pixel_pct"] = round(hot_pct, 2)

        # ── Hotspot region ratio ──────────────────────────────────────────
        if hot_count > 0 and ela_mean > 0:
            hotspot_mean = float(np.mean(ela_amplified[hot_mask]))
            hotspot_ratio = hotspot_mean / ela_mean
            result["hotspot_ratio"] = round(hotspot_ratio, 2)

            if hotspot_ratio > _HOT_RATIO_ALERT:
                result["flags"].append(
                    f"ELA_HOTSPOT: localised region is {hotspot_ratio:.1f}× "
                    f"brighter than background — possible pixel editing"
                )
        else:
            result["hotspot_ratio"] = 0.0

        if hot_pct > _HOT_PERCENTAGE_ALERT:
            result["flags"].append(
                f"ELA_HOT_AREA: {hot_pct:.1f}% of pixels are above "
                f"threshold — widespread compression inconsistency"
            )

        # ── SSIM (Structural Similarity) ──────────────────────────────────
        try:
            from skimage.metrics import structural_similarity as ssim
            original_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
            recompressed_gray = cv2.cvtColor(recompressed, cv2.COLOR_BGR2GRAY)
            ssim_val = ssim(original_gray, recompressed_gray)
            result["ssim"] = round(float(ssim_val), 4)

            # Very low SSIM after mild recompression → unusual
            if ssim_val < 0.90:
                result["flags"].append(
                    f"LOW_SSIM: structural similarity {ssim_val:.4f} "
                    "after 95% recompression — unusual compression artifacts"
                )
        except Exception as exc:
            logger.debug("SSIM computation failed: %s", exc)
            result["ssim"] = -1.0

    except Exception as exc:
        logger.warning("ELA analysis failed: %s", exc)
        result["flags"] = [f"ELA_FAILED: {exc}"]
        result["passed"] = False
        return result

    result["passed"] = len(result["flags"]) == 0
    return result
