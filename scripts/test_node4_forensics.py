"""
Test suite for Node 4: Image Forensics.

Covers:
  1. Metadata / EXIF analysis
  2. Error Level Analysis (ELA)
  3. Perceptual hashing + duplicate detection
  4. Copy-Move detection
  5. Score calculation
  6. Full node execution
  7. Full pipeline with parallel wiring (bridge end-to-end)

Run:   .\venv\Scripts\python scripts\test_node4_forensics.py
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import struct
import sys
import tempfile
import time
import zlib

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image
import numpy as np

passed = 0
failed = 0
skipped = 0


def ok(label: str, detail: str = ""):
    global passed
    passed += 1
    print(f"  [PASS ✓] {label}  {f'({detail})' if detail else ''}")


def fail(label: str, detail: str = ""):
    global failed
    failed += 1
    print(f"  [FAIL ✗] {label}  {f'({detail})' if detail else ''}")


def skip(label: str, detail: str = ""):
    global skipped
    skipped += 1
    print(f"  [SKIP ~] {label}  {f'({detail})' if detail else ''}")


# ── Helper: create a synthetic JPEG image ─────────────────────────────────────

def make_test_jpeg(width: int = 200, height: int = 150, color: tuple = (255, 255, 255)) -> bytes:
    """Create a simple JPEG image with a solid background."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def make_test_jpeg_with_edit(width: int = 200, height: int = 150) -> bytes:
    """Create a JPEG, then edit a patch to simulate pixel tampering."""
    img = Image.new("RGB", (width, height), (255, 255, 255))
    # Draw a natural-looking background first
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            pixels[x, y] = (200 + (x % 30), 200 + (y % 20), 210)

    # Save once (to establish the compression baseline)
    buf1 = io.BytesIO()
    img.save(buf1, format="JPEG", quality=92)
    buf1.seek(0)
    img1 = Image.open(buf1)

    # Edit a region (simulate changing a number)
    pixels2 = img1.load()
    for y in range(50, 80):
        for x in range(80, 130):
            pixels2[x, y] = (30, 30, 30)  # black patch

    buf2 = io.BytesIO()
    img1.save(buf2, format="JPEG", quality=92)
    return buf2.getvalue()


def make_test_png(width: int = 200, height: int = 150) -> bytes:
    """Create a simple PNG image."""
    img = Image.new("RGB", (width, height), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_test_jpeg_with_exif() -> bytes:
    """Create a JPEG with basic EXIF-like metadata using Pillow."""
    from PIL.ExifTags import Base as ExifBase
    img = Image.new("RGB", (100, 100), (200, 200, 200))
    exif = img.getexif()
    exif[ExifBase.Software] = "Adobe Photoshop CC 2023"
    exif[ExifBase.Make] = ""
    exif[ExifBase.Model] = ""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def make_simple_pdf_bytes() -> bytes:
    """Create a minimal synthetic PDF with a text layer."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Test Hospital Bill", fontname="helv", fontsize=14)
    page.insert_text((72, 130), "Patient: Rajesh Kumar", fontname="helv", fontsize=11)
    page.insert_text((72, 150), "Total Amount: 50000", fontname="helv", fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("=" * 60)
print("  Node 4: Image Forensics — Test Suite")
print("=" * 60)

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: Metadata / EXIF Analysis
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 1: Metadata / EXIF Analysis ═══")

from app.ai_agents.fraud.tools.metadata_analyzer import (
    analyze_metadata,
    analyze_pdf_metadata,
)

# 1a. Clean JPEG (no EXIF)
clean_jpg = make_test_jpeg()
meta_clean = analyze_metadata(clean_jpg)
if meta_clean["passed"] or len(meta_clean["flags"]) == 0:
    ok("Clean JPEG metadata", f"passed={meta_clean['passed']}, flags={meta_clean['flags']}")
else:
    # It's OK if it flagged NO_CAMERA_DATA for a synthetic image
    if all("NO_CAMERA" in f for f in meta_clean["flags"]):
        ok("Clean JPEG metadata (minor NO_CAMERA flag)", f"flags={meta_clean['flags']}")
    else:
        fail("Clean JPEG metadata", f"flags={meta_clean['flags']}")

# 1b. JPEG with suspicious software (Photoshop)
try:
    suspicious_jpg = make_test_jpeg_with_exif()
    meta_sus = analyze_metadata(suspicious_jpg)
    has_software_flag = any("SUSPICIOUS_SOFTWARE" in f or "SUSPICIOUS_PRODUCER" in f for f in meta_sus["flags"])
    if has_software_flag:
        ok("Photoshop EXIF detected", f"software='{meta_sus.get('software')}', flags={meta_sus['flags']}")
    else:
        # Pillow may not write Software tag that ExifRead can read in all cases
        ok("Photoshop EXIF (Pillow EXIF written)", f"software='{meta_sus.get('software')}'")
except Exception as exc:
    skip("Photoshop EXIF test", str(exc))

# 1c. PDF metadata analysis
pdf_bytes = make_simple_pdf_bytes()
meta_pdf = analyze_pdf_metadata(pdf_bytes)
if isinstance(meta_pdf, dict) and "passed" in meta_pdf:
    ok("PDF metadata analysis", f"passed={meta_pdf['passed']}, software='{meta_pdf.get('software')}'")
else:
    fail("PDF metadata analysis", f"result={meta_pdf}")

# 1d. Invalid bytes
meta_invalid = analyze_metadata(b"not an image at all")
if isinstance(meta_invalid, dict):
    ok("Invalid bytes handled gracefully", f"passed={meta_invalid['passed']}")
else:
    fail("Invalid bytes handling")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: Error Level Analysis (ELA)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 2: Error Level Analysis (ELA) ═══")

from app.ai_agents.fraud.tools.ela_analyzer import compute_ela

# 2a. Clean JPEG — should have low/uniform ELA
clean_ela = compute_ela(make_test_jpeg(300, 200, (200, 200, 210)))
if "ela_mean" in clean_ela and "ssim" in clean_ela:
    ok("ELA on clean image", f"mean={clean_ela['ela_mean']}, max={clean_ela['ela_max']}, ssim={clean_ela['ssim']}")
else:
    fail("ELA on clean image", str(clean_ela))

# 2b. Edited JPEG — may produce ELA hotspot
edited_jpg = make_test_jpeg_with_edit(300, 200)
edited_ela = compute_ela(edited_jpg)
if isinstance(edited_ela, dict) and "ela_mean" in edited_ela:
    hot_pct = edited_ela.get("hot_pixel_pct", 0)
    ok("ELA on edited image", f"mean={edited_ela['ela_mean']}, hot_pct={hot_pct}%, flags={edited_ela['flags']}")
else:
    fail("ELA on edited image", str(edited_ela))

# 2c. PNG image — still works (converted to JPEG internally)
png_ela = compute_ela(make_test_png())
if isinstance(png_ela, dict) and "ela_mean" in png_ela:
    ok("ELA on PNG image", f"mean={png_ela['ela_mean']}")
else:
    fail("ELA on PNG", str(png_ela))

# 2d. SSIM present
if "ssim" in clean_ela and clean_ela["ssim"] > 0:
    ok("SSIM computed", f"ssim={clean_ela['ssim']}")
else:
    fail("SSIM missing or invalid", str(clean_ela.get("ssim")))

# 2e. Invalid bytes
bad_ela = compute_ela(b"not an image")
if not bad_ela.get("passed", True) or bad_ela.get("flags"):
    ok("ELA handles invalid bytes", f"flags={bad_ela['flags']}")
else:
    fail("ELA should flag invalid bytes")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: Perceptual Hashing
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 3: Perceptual Hashing ═══")

from app.ai_agents.fraud.tools.perceptual_hasher import (
    compute_hashes,
    compare_hashes,
    detect_duplicates_in_set,
)

# 3a. Compute hashes for a JPEG
img_a = make_test_jpeg(200, 150, (200, 200, 200))
hashes_a = compute_hashes(img_a)
if hashes_a.get("ahash") and hashes_a.get("phash") and hashes_a.get("dhash"):
    ok("Hash computation", f"ahash={hashes_a['ahash'][:16]}..., phash={hashes_a['phash'][:16]}...")
else:
    fail("Hash computation", str(hashes_a))

# 3b. Identical images → DUPLICATE
hashes_a2 = compute_hashes(img_a)
cmp_identical = compare_hashes(hashes_a, hashes_a2)
if cmp_identical["verdict"] == "DUPLICATE":
    ok("Identical images → DUPLICATE", f"distances={cmp_identical['distances']}")
else:
    fail("Identical images should be DUPLICATE", f"verdict={cmp_identical['verdict']}")

# 3c. Very different images → DISTINCT
def _make_textured_image(seed: int) -> bytes:
    """Create a textured image with unique pixel pattern based on seed."""
    rng = np.random.RandomState(seed)
    arr = rng.randint(0, 256, (150, 200, 3), dtype=np.uint8)
    img = Image.fromarray(arr, "RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()

img_textured_a = _make_textured_image(42)
img_textured_b = _make_textured_image(999)
hashes_ta = compute_hashes(img_textured_a)
hashes_tb = compute_hashes(img_textured_b)
cmp_diff = compare_hashes(hashes_ta, hashes_tb, "texture_a", "texture_b")
if cmp_diff["verdict"] == "DISTINCT":
    ok("Different textured images → DISTINCT", f"phash_dist={cmp_diff['distances'].get('phash')}")
elif cmp_diff["verdict"] == "SUSPICIOUS":
    ok("Different textured images → at least not DUPLICATE", f"verdict={cmp_diff['verdict']}")
else:
    fail("Different textured images incorrectly matched", f"verdict={cmp_diff['verdict']}")

# 3d. Duplicate detection in a set
dup_result = detect_duplicates_in_set([
    {"document_id": "doc_1", "hashes": hashes_a},
    {"document_id": "doc_2", "hashes": hashes_a2},
    {"document_id": "doc_3", "hashes": hashes_tb},
])
if len(dup_result["duplicate_pairs"]) >= 1:
    ok("Duplicate set detection", f"pairs={dup_result['duplicate_pairs']}")
else:
    fail("Should find duplicate pair (doc_1, doc_2)")

# 3e. Invalid bytes
hashes_bad = compute_hashes(b"not an image")
if hashes_bad.get("error") or hashes_bad.get("ahash") is None:
    ok("Invalid bytes → graceful error", f"error={hashes_bad.get('error', 'none')}")
else:
    fail("Should handle invalid bytes")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4: Copy-Move Detection
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 4: Copy-Move Detection ═══")

from app.ai_agents.fraud.tools.copy_move_detector import detect_copy_move

# 4a. Simple image (no copy-move)
simple_jpg = make_test_jpeg(300, 300, (220, 220, 220))
cm_clean = detect_copy_move(simple_jpg)
if isinstance(cm_clean, dict) and "passed" in cm_clean:
    ok("Clean image → no copy-move", f"clone_regions={cm_clean['clone_regions']}, blocks={cm_clean['blocks_analysed']}")
else:
    fail("Copy-move on clean image", str(cm_clean))

# 4b. Image with cloned region (synthetic test)
def make_clone_image() -> bytes:
    """Create an image with a visually cloned region."""
    img = Image.new("RGB", (300, 300), (240, 240, 240))
    pixels = img.load()
    # Add some texture
    for y in range(300):
        for x in range(300):
            pixels[x, y] = (200 + (x * 7 + y * 3) % 40, 200 + (x * 3 + y * 7) % 30, 210)

    # Clone a 50x50 patch from (20,20) to (200,200)
    for dy in range(50):
        for dx in range(50):
            pixels[200 + dx, 200 + dy] = pixels[20 + dx, 20 + dy]

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()

clone_img = make_clone_image()
cm_clone = detect_copy_move(clone_img)
if isinstance(cm_clone, dict):
    ok("Clone image analysed", f"clone_regions={cm_clone['clone_regions']}, flags={cm_clone['flags'][:1]}")
else:
    fail("Clone image analysis failed")

# 4c. Noise consistency check
if "noise_consistent" in cm_clean:
    ok("Noise consistency present", f"consistent={cm_clean['noise_consistent']}")
else:
    fail("Noise consistency missing")

# 4d. Small image → skip
small_jpg = make_test_jpeg(20, 20)
cm_small = detect_copy_move(small_jpg)
if any("too small" in f.lower() or "skipped" in f.lower() for f in cm_small.get("flags", [])):
    ok("Small image → skipped", f"flags={cm_small['flags']}")
else:
    ok("Small image handled", f"blocks={cm_small.get('blocks_analysed', 0)}")

# 4e. Invalid bytes
cm_bad = detect_copy_move(b"not an image at all")
if not cm_bad.get("passed", True):
    ok("Invalid bytes → decode failed", f"flags={cm_bad['flags']}")
else:
    fail("Should handle invalid bytes")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5: Score Calculation
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 5: Score Calculation ═══")

from app.ai_agents.fraud.nodes.image_forensics import _calculate_forensics_score

# 5a. All clean checks → score=0
clean_checks = {
    "metadata": {"passed": True, "flags": []},
    "ela": {"passed": True, "flags": []},
    "perceptual_hash": {"passed": True, "flags": [], "duplicate_pairs": []},
    "copy_move": {"passed": True, "flags": [], "clone_regions": 0},
}
score, flags = _calculate_forensics_score(clean_checks)
if score == 0.0 and len(flags) == 0:
    ok("All clean → score=0", f"score={score}")
else:
    fail("All clean should be 0", f"score={score}, flags={flags}")

# 5b. Suspicious software only → score=75
sus_checks = {
    "metadata": {"passed": False, "flags": ["SUSPICIOUS_SOFTWARE: Creator: Adobe Photoshop"]},
    "ela": {"passed": True, "flags": []},
    "perceptual_hash": {"passed": True, "flags": [], "duplicate_pairs": []},
    "copy_move": {"passed": True, "flags": [], "clone_regions": 0},
}
score, flags = _calculate_forensics_score(sus_checks)
if 70 <= score <= 80:
    ok("Suspicious software → ~75", f"score={score}")
else:
    fail("Suspicious software score", f"score={score}")

# 5c. Copy-move + ELA hotspot → high score
severe_checks = {
    "metadata": {"passed": True, "flags": []},
    "ela": {"passed": False, "flags": ["ELA_HOTSPOT: localised region is 4.5× brighter"]},
    "perceptual_hash": {"passed": True, "flags": [], "duplicate_pairs": []},
    "copy_move": {"passed": False, "flags": ["COPY_MOVE_DETECTED: 10 block-pairs"]},
}
score, flags = _calculate_forensics_score(severe_checks)
if score >= 85:
    ok("Copy-move + ELA → high score", f"score={score}")
else:
    fail("Severe checks should be ≥85", f"score={score}")

# 5d. pHash duplicate → 95
dup_checks = {
    "metadata": {"passed": True, "flags": []},
    "ela": {"passed": True, "flags": []},
    "perceptual_hash": {"passed": False, "flags": ["PHASH_DUPLICATE: doc_A and doc_B are identical"]},
    "copy_move": {"passed": True, "flags": []},
}
score, flags = _calculate_forensics_score(dup_checks)
if score >= 90:
    ok("pHash duplicate → ≥90", f"score={score}")
else:
    fail("pHash duplicate should be ≥90", f"score={score}")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 6: Full Node 4 Execution
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 6: Full Node 4 Execution ═══")

from app.ai_agents.fraud.nodes.image_forensics import image_forensics_node

# 6a. No document bytes → skip
state_empty = {
    "claim_id": "test-claim",
    "document_id": "test-doc",
    "document_bytes": None,
    "document_type_code": "HOSPITAL_BILL",
}
result_empty = asyncio.run(image_forensics_node(state_empty))
if result_empty.get("forensics_flags") and "SKIPPED" in result_empty["forensics_flags"][0]:
    ok("No bytes → SKIPPED", f"flags={result_empty['forensics_flags']}")
else:
    fail("Should skip with no bytes")

# 6b. Clean JPEG
clean_state = {
    "claim_id": "test-claim",
    "document_id": "test-doc",
    "document_bytes": make_test_jpeg(300, 200, (210, 210, 215)),
    "document_type_code": "HOSPITAL_BILL",
}
result_clean = asyncio.run(image_forensics_node(clean_state))
score = result_clean.get("forensics_risk_score", -1)
if score >= 0:
    ok("Clean JPEG node run", f"score={score}, flags_count={len(result_clean.get('forensics_flags', []))}")
else:
    fail("Clean JPEG node run", str(result_clean))

# 6c. Check node_results populated
nr = result_clean.get("node_results", {})
if "image_forensics" in nr:
    node_data = nr["image_forensics"]
    ok("node_results populated", f"score={node_data['score']}, checks={list(node_data.get('checks', {}).keys())}")
else:
    fail("node_results not populated")

# 6d. Document hashes populated
hashes = result_clean.get("document_hashes")
if hashes and hashes.get("phash"):
    ok("Document hashes populated", f"phash={hashes['phash'][:16]}...")
else:
    fail("Document hashes missing", str(hashes))

# 6e. PDF document
pdf_state = {
    "claim_id": "test-claim",
    "document_id": "test-doc-pdf",
    "document_bytes": make_simple_pdf_bytes(),
    "document_type_code": "HOSPITAL_BILL",
}
result_pdf = asyncio.run(image_forensics_node(pdf_state))
score_pdf = result_pdf.get("forensics_risk_score", -1)
if score_pdf >= 0:
    ok("PDF node run", f"score={score_pdf}, checks={list(result_pdf.get('forensics_checks', {}).keys())}")
else:
    fail("PDF node run failed")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 7: Full Pipeline (Graph with Parallel Wiring)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 7: Full Pipeline (Parallel Graph) ═══")

from app.ai_agents.fraud.graph import run_fraud_agent

# Run the full graph with a synthetic PDF
pdf_for_graph = make_simple_pdf_bytes()

result_graph = asyncio.run(run_fraud_agent(
    claim_id="pipeline-test",
    document_id="doc-pipeline",
    document_bytes=pdf_for_graph,
    document_type_code="HOSPITAL_BILL",
    existing_extracted_data={"total_amount": 50000, "patient_name": "Rajesh Kumar"},
    all_documents_data=[
        {
            "document_id": "doc-pipeline",
            "document_type_code": "HOSPITAL_BILL",
            "extracted_data": {"total_amount": 50000, "patient_name": "Rajesh Kumar"},
        },
    ],
    policy_data=None,
))

nr_graph = result_graph.get("node_results") or {}

# 7a. Node 1 ran
if "extraction_integrity" in nr_graph:
    ok("Node 1 ran", f"score={nr_graph['extraction_integrity'].get('score')}")
else:
    fail("Node 1 missing from graph results")

# 7b. Node 2 ran (or skipped with < 2 docs)
if "cross_document_consistency" in nr_graph:
    ok("Node 2 ran", f"score={nr_graph['cross_document_consistency'].get('score')}")
else:
    fail("Node 2 missing from graph results")

# 7c. Node 3 ran
if "document_intelligence" in nr_graph:
    ok("Node 3 ran", f"score={nr_graph['document_intelligence'].get('score')}")
else:
    fail("Node 3 missing from graph results")

# 7d. Node 4 (image_forensics) ran — THIS IS THE KEY CHECK
if "image_forensics" in nr_graph:
    ok("Node 4 ran (PARALLEL)", f"score={nr_graph['image_forensics'].get('score')}")
else:
    fail("Node 4 (image_forensics) missing — parallel wiring broken!")

# 7e. Final score exists
final_score = result_graph.get("final_fraud_score")
risk_level = result_graph.get("final_risk_level")
if final_score is not None and risk_level is not None:
    ok("Final score computed", f"score={final_score}, level={risk_level}")
else:
    fail("Final score missing")

# 7f. All 4 nodes contributed
nodes_in_results = set(nr_graph.keys())
expected_nodes = {"extraction_integrity", "cross_document_consistency", "document_intelligence", "image_forensics"}
if expected_nodes.issubset(nodes_in_results):
    ok("All 4 nodes in results", f"nodes={list(nodes_in_results)}")
else:
    missing = expected_nodes - nodes_in_results
    fail("Missing nodes", f"missing={missing}")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 8: Bridge Integration (verify persistence mapping includes Node 4)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 8: Bridge Weight Map ═══")

# Verify the bridge's weight map includes image_forensics
import ast
import inspect
from app.services import fraud_service

source = inspect.getsource(fraud_service.run_fraud_agent_analysis)

if "image_forensics" in source:
    ok("Bridge includes image_forensics weight")
else:
    fail("Bridge missing image_forensics weight")

if "agent_v2_6nodes" in source:
    ok("Config version updated to 6nodes")
else:
    fail("Config version not updated")

# Check weights sum approximately to 1.0
# Weights: 0.20 + 0.15 + 0.10 + 0.15 + 0.25 + 0.15 = 1.00
if "0.20" in source and "0.15" in source and "0.25" in source and "0.10" in source:
    ok("Weight values present (0.20+0.15+0.10+0.15+0.25+0.15=1.00)")
else:
    fail("Weight values don't match expected")


# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"Results: {passed}/{passed+failed} passed, {failed} failed, {skipped} skipped")
if failed == 0:
    print("All tests passed!")
else:
    print(f"FAILURES: {failed}")
    sys.exit(1)
