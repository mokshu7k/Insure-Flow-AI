"""
Node 4: Image Forensics — Zero Trust Pixel Analysis.

This node treats every document as a potentially tampered digital artifact.
While Gemini (Node 1) reads the "what", this node analyses the "how" — the
invisible digital fabric of the image: metadata, compression artefacts,
perceptual hashes, and copy-move traces.

Runs in **parallel** with Nodes 1→2→3 in the LangGraph topology because
it requires only ``document_bytes`` (no Gemini output needed).

Sub-checks:
  1. Metadata / EXIF Analysis   — software tags, date anomalies, camera info
  2. Error Level Analysis (ELA) — JPEG compression inconsistencies
  3. Perceptual Hashing (pHash) — template-farm / duplicate detection
  4. Copy-Move Detection        — DCT block-matching for cloned regions

All checks are deterministic Python + OpenCV — zero LLM calls.
"""
from __future__ import annotations

import io
import logging
import time
from typing import Any

from langchain_core.messages import AIMessage
from PIL import Image

from app.ai_agents.fraud.state import FraudAgentState

logger = logging.getLogger(__name__)

# ── Risk weights per sub-check ────────────────────────────────────────────────
RISK_WEIGHTS = {
    "suspicious_software":   75,   # Photoshop / Canva / Illustrator
    "date_anomaly":          60,   # ModifyDate < CreateDate
    "no_camera_data":        30,   # No camera for "scanned" doc
    "low_dpi":               25,   # Suspiciously low resolution
    "ela_hotspot":           85,   # Localised editing detected
    "ela_hot_area":          65,   # Widespread compression anomaly
    "low_ssim":              50,   # Structural inconsistency
    "phash_duplicate":       95,   # Identical to known document
    "phash_near_duplicate":  80,   # Same template, minor edits
    "phash_suspicious":      45,   # Visually similar, needs review
    "copy_move":             90,   # Cloned regions detected
    "noise_inconsistency":   70,   # Splice boundary detected
}


def _calculate_forensics_score(checks: dict[str, dict[str, Any]]) -> tuple[float, list[str]]:
    """Calculate image forensics risk score (0–100)."""
    penalties: list[float] = []
    all_flags: list[str] = []

    # ── Metadata ──────────────────────────────────────────────────────────
    meta = checks.get("metadata", {})
    meta_flags = meta.get("flags", [])
    for flag in meta_flags:
        flag_upper = flag.upper()
        if "SUSPICIOUS_SOFTWARE" in flag_upper or "SUSPICIOUS_PRODUCER" in flag_upper:
            penalties.append(RISK_WEIGHTS["suspicious_software"])
        elif "DATE_ANOMALY" in flag_upper or "DATE_GAP" in flag_upper:
            penalties.append(RISK_WEIGHTS["date_anomaly"])
        elif "NO_CAMERA_DATA" in flag_upper:
            penalties.append(RISK_WEIGHTS["no_camera_data"])
        elif "LOW_DPI" in flag_upper:
            penalties.append(RISK_WEIGHTS["low_dpi"])
    all_flags.extend(meta_flags)

    # ── ELA ───────────────────────────────────────────────────────────────
    ela = checks.get("ela", {})
    ela_flags = ela.get("flags", [])
    for flag in ela_flags:
        flag_upper = flag.upper()
        if "ELA_HOTSPOT" in flag_upper:
            penalties.append(RISK_WEIGHTS["ela_hotspot"])
        elif "ELA_HOT_AREA" in flag_upper:
            penalties.append(RISK_WEIGHTS["ela_hot_area"])
        elif "LOW_SSIM" in flag_upper:
            penalties.append(RISK_WEIGHTS["low_ssim"])
    all_flags.extend(ela_flags)

    # ── Perceptual Hashing ────────────────────────────────────────────────
    phash = checks.get("perceptual_hash", {})
    phash_flags = phash.get("flags", [])
    for flag in phash_flags:
        flag_upper = flag.upper()
        if "DUPLICATE" in flag_upper and "NEAR" not in flag_upper:
            penalties.append(RISK_WEIGHTS["phash_duplicate"])
        elif "NEAR_DUPLICATE" in flag_upper:
            penalties.append(RISK_WEIGHTS["phash_near_duplicate"])
        elif "SUSPICIOUS" in flag_upper:
            penalties.append(RISK_WEIGHTS["phash_suspicious"])
    all_flags.extend(phash_flags)

    # ── Copy-Move ─────────────────────────────────────────────────────────
    cm = checks.get("copy_move", {})
    cm_flags = cm.get("flags", [])
    for flag in cm_flags:
        flag_upper = flag.upper()
        if "COPY_MOVE_DETECTED" in flag_upper:
            penalties.append(RISK_WEIGHTS["copy_move"])
        elif "NOISE_INCONSISTENCY" in flag_upper:
            penalties.append(RISK_WEIGHTS["noise_inconsistency"])
    all_flags.extend(cm_flags)

    if not penalties:
        return 0.0, all_flags

    # Max-dominant scoring with diminishing additions
    max_penalty = max(penalties)
    others = sum(p for p in penalties if p != max_penalty)
    additional = min(25.0, others * 0.2)
    score = min(100.0, max_penalty + additional)

    return round(score, 1), all_flags


def _get_image_bytes_for_forensics(
    document_bytes: bytes,
    document_type_code: str,
) -> list[bytes]:
    """Convert document bytes to image bytes for forensics analysis.

    If the document is a PDF, renders each page as a JPEG image.
    If it's already an image, returns it directly.

    Returns a list of image byte arrays (one per page/image).
    """
    images: list[bytes] = []

    # Try as PDF first
    try:
        import fitz
        doc = fitz.open(stream=document_bytes, filetype="pdf")
        for page in doc:
            mat = fitz.Matrix(2, 2)  # 2× zoom
            pix = page.get_pixmap(matrix=mat)
            # Convert to JPEG for ELA (needs lossy compression)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=95)
            images.append(buf.getvalue())
        doc.close()
        if images:
            return images
    except Exception:
        pass  # Not a PDF, try as image

    # Try as direct image
    try:
        img = Image.open(io.BytesIO(document_bytes))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=95)
        images.append(buf.getvalue())
    except Exception as exc:
        logger.warning("Cannot convert document to image for forensics: %s", exc)

    return images


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  THE NODE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def image_forensics_node(
    state: FraudAgentState,
    config: dict | None = None,
) -> dict[str, Any]:
    """LangGraph node — image forensics analysis.

    Runs in PARALLEL with Nodes 1→2→3 because it only needs
    ``document_bytes``, not any Gemini extraction output.

    Reads:
        state["document_bytes"]
        state["document_type_code"]
        state["all_documents_data"]   (optional — for cross-doc pHash)

    Writes:
        forensics_checks, forensics_risk_score, forensics_flags,
        document_hashes, node_results (partial), messages
    """
    from app.ai_agents.fraud.tools.metadata_analyzer import (
        analyze_metadata,
        analyze_pdf_metadata,
    )
    from app.ai_agents.fraud.tools.ela_analyzer import compute_ela
    from app.ai_agents.fraud.tools.perceptual_hasher import (
        compute_hashes,
        detect_duplicates_in_set,
    )
    from app.ai_agents.fraud.tools.copy_move_detector import detect_copy_move

    claim_id = state.get("claim_id", "unknown")
    doc_id = state.get("document_id", "unknown")
    doc_bytes = state.get("document_bytes")
    doc_type = state.get("document_type_code", "UNKNOWN")

    logger.info(
        "Node 4 [Image Forensics] starting — claim=%s doc=%s type=%s",
        claim_id, doc_id, doc_type,
    )
    t_start = time.perf_counter()

    # ── Defaults (in case of early exit) ──────────────────────────────────────
    result: dict[str, Any] = {
        "forensics_checks": {},
        "forensics_risk_score": 0.0,
        "forensics_flags": [],
        "document_hashes": None,
        "messages": [AIMessage(content="Node 4 [Image Forensics]: starting…")],
    }

    if not doc_bytes:
        logger.warning("No document bytes provided — skipping image forensics")
        result["forensics_flags"] = ["SKIPPED: no document bytes available"]
        result["messages"] = [
            AIMessage(content="Node 4 [Image Forensics]: SKIPPED — no document bytes.")
        ]
        # Merge into node_results
        existing_nr = state.get("node_results") or {}
        existing_nr["image_forensics"] = {
            "score": 0.0,
            "flags": result["forensics_flags"],
            "skipped": True,
        }
        result["node_results"] = existing_nr
        return result

    checks: dict[str, Any] = {}

    try:
        # ── Step 1: Metadata / EXIF Analysis ──────────────────────────────────────
        logger.info("Step 1: Metadata / EXIF analysis…")
        is_pdf = False
        try:
            import fitz
            try:
                doc = fitz.open(stream=doc_bytes, filetype="pdf")
                doc.close()
                is_pdf = True
            except Exception:
                is_pdf = False
        except ImportError:
            is_pdf = False

        if is_pdf:
            checks["metadata"] = analyze_pdf_metadata(doc_bytes)
        else:
            checks["metadata"] = analyze_metadata(doc_bytes)

        # ── Step 2: Convert to image bytes for pixel-level analysis ───────────────
        logger.info("Step 2: Converting document to image(s) for pixel analysis…")
        image_list = _get_image_bytes_for_forensics(doc_bytes, doc_type)

        if not image_list:
            logger.warning("Could not extract any images from document")
            checks["ela"] = {"passed": True, "skipped": True, "skip_reason": "no_images"}
            checks["copy_move"] = {"passed": True, "skipped": True, "skip_reason": "no_images"}
            checks["perceptual_hash"] = {"passed": True, "skipped": True, "skip_reason": "no_images"}
        else:
            # Use the first page for ELA and copy-move (primary page)
            primary_image = image_list[0]

            # ── Step 3: Error Level Analysis ──────────────────────────────────
            logger.info("Step 3: Error Level Analysis (ELA)…")
            checks["ela"] = compute_ela(primary_image)

            # ── Step 4: Copy-Move Detection ───────────────────────────────────
            logger.info("Step 4: Copy-Move / Splicing detection…")
            checks["copy_move"] = detect_copy_move(primary_image)

            # ── Step 5: Perceptual Hashing ────────────────────────────────────
            logger.info("Step 5: Computing perceptual hashes…")
            target_hashes = compute_hashes(primary_image)
            result["document_hashes"] = target_hashes

            # Cross-document duplicate detection
            all_docs = state.get("all_documents_data") or []
            # Build hash list: target document + render first page of each other doc
            hash_set: list[dict[str, Any]] = [
                {"document_id": doc_id, "hashes": target_hashes}
            ]

            for other_doc in all_docs:
                other_id = other_doc.get("document_id", "")
                if other_id == doc_id:
                    continue
                # We don't have other docs' bytes in this node, so cross-doc
                # pHash comparison is limited to the documents whose bytes
                # we can access.  For now, we store the target's hashes so
                # they can be compared externally.  If all_documents are
                # images passed via state, we could compare them too.

            # If we rendered multiple pages, compare pages to each other
            if len(image_list) > 1:
                for idx, page_img in enumerate(image_list[1:], start=2):
                    page_hashes = compute_hashes(page_img)
                    hash_set.append({
                        "document_id": f"{doc_id}_page_{idx}",
                        "hashes": page_hashes,
                    })

            phash_result = detect_duplicates_in_set(hash_set)
            checks["perceptual_hash"] = phash_result

        result["forensics_checks"] = checks

        # ── Step 6: Calculate composite forensics score ───────────────────────────
        logger.info("Step 6: Calculating forensics risk score…")
        score, flags = _calculate_forensics_score(checks)
        result["forensics_risk_score"] = score
        result["forensics_flags"] = flags

        # ── Build node_results entry ──────────────────────────────────────────────
        elapsed = time.perf_counter() - t_start

        existing_nr = state.get("node_results") or {}
        existing_nr["image_forensics"] = {
            "score": score,
            "flags": flags,
            "checks": {
                "metadata": {
                    "passed": checks.get("metadata", {}).get("passed"),
                    "has_exif": checks.get("metadata", {}).get("has_exif"),
                    "software": checks.get("metadata", {}).get("software"),
                    "flag_count": len(checks.get("metadata", {}).get("flags", [])),
                },
                "ela": {
                    "passed": checks.get("ela", {}).get("passed"),
                    "skipped": checks.get("ela", {}).get("skipped", False),
                    "ela_mean": checks.get("ela", {}).get("ela_mean"),
                    "hotspot_ratio": checks.get("ela", {}).get("hotspot_ratio"),
                    "hot_pixel_pct": checks.get("ela", {}).get("hot_pixel_pct"),
                    "ssim": checks.get("ela", {}).get("ssim"),
                },
                "perceptual_hash": {
                    "passed": checks.get("perceptual_hash", {}).get("passed"),
                    "skipped": checks.get("perceptual_hash", {}).get("skipped", False),
                    "duplicate_pairs": len(
                        checks.get("perceptual_hash", {}).get("duplicate_pairs", [])
                    ),
                },
                "copy_move": {
                    "passed": checks.get("copy_move", {}).get("passed"),
                    "skipped": checks.get("copy_move", {}).get("skipped", False),
                    "clone_regions": checks.get("copy_move", {}).get("clone_regions", 0),
                    "noise_consistent": checks.get("copy_move", {}).get("noise_consistent"),
                },
            },
            "elapsed_seconds": round(elapsed, 2),
        }
        result["node_results"] = existing_nr

        # ── Summary message ───────────────────────────────────────────────────────
        status = "CLEAN" if score < 20 else "SUSPICIOUS" if score < 60 else "HIGH_RISK"
        sub_summaries = []
        if not checks.get("metadata", {}).get("skipped"):
            sub_summaries.append(
                f"metadata={'PASS' if checks.get('metadata', {}).get('passed') else 'FAIL'}"
            )
        if not checks.get("ela", {}).get("skipped"):
            sub_summaries.append(
                f"ELA={'PASS' if checks.get('ela', {}).get('passed') else 'FAIL'}"
            )
        if not checks.get("copy_move", {}).get("skipped"):
            sub_summaries.append(
                f"copy_move={'PASS' if checks.get('copy_move', {}).get('passed') else 'FAIL'}"
            )
        if not checks.get("perceptual_hash", {}).get("skipped"):
            sub_summaries.append(
                f"pHash={'PASS' if checks.get('perceptual_hash', {}).get('passed') else 'FAIL'}"
            )

        summary = (
            f"Node 4 [Image Forensics] complete — "
            f"score={score}/100 ({status}), "
            f"{', '.join(sub_summaries) if sub_summaries else 'no checks ran'}, "
            f"elapsed={elapsed:.2f}s"
        )
        logger.info(summary)
        result["messages"] = [AIMessage(content=summary)]

    except Exception as exc:
        elapsed = time.perf_counter() - t_start
        logger.error("Node 4 [Image Forensics] crashed: %s", exc, exc_info=True)
        existing_nr = state.get("node_results") or {}
        existing_nr["image_forensics"] = {
            "score": 0.0,
            "flags": [f"ERROR: {exc}"],
            "error": str(exc),
            "elapsed_seconds": round(elapsed, 2),
        }
        result["node_results"] = existing_nr
        result["forensics_flags"] = [f"ERROR: {exc}"]
        result["messages"] = [
            AIMessage(content=f"Node 4 [Image Forensics] — error: {exc}")
        ]

    return result
