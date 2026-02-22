"""
Test script for Node 1: Extraction Integrity.

This script tests each component of the three-way reconciliation pipeline
independently, then runs the full node via the LangGraph agent.

Usage:
    python scripts/test_node1_integrity.py <path_to_pdf>

If no PDF is provided, it creates a synthetic test PDF to verify
the pipeline works end-to-end.
"""
from __future__ import annotations

import asyncio
import json
import sys
import os
import logging

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_node1")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Helper: Create a synthetic test PDF
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def create_test_pdf() -> bytes:
    """Create a simple hospital bill PDF for testing."""
    import fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    # Hospital header
    page.insert_text((50, 50), "APOLLO HOSPITAL", fontsize=16, fontname="helv")
    page.insert_text((50, 70), "Bill No: APL-2026-001234", fontsize=10)
    page.insert_text((50, 85), "Date: 15/02/2026", fontsize=10)

    # Patient info
    page.insert_text((50, 120), "Patient Name: Rajesh Kumar", fontsize=11)
    page.insert_text((50, 135), "Admission Date: 01/02/2026", fontsize=10)
    page.insert_text((50, 150), "Discharge Date: 10/02/2026", fontsize=10)

    # Line items
    y = 190
    page.insert_text((50, y), "─" * 60, fontsize=10)
    y += 15
    page.insert_text((50, y), "Description", fontsize=10, fontname="helv")
    page.insert_text((400, y), "Amount (Rs.)", fontsize=10, fontname="helv")

    items = [
        ("ICU Charges (3 days @ 14,000/day)", "42,000"),
        ("Surgery Charges", "60,000"),
        ("Medicine & Consumables", "18,500"),
        ("Doctor Consultation Fees", "12,000"),
        ("Lab Tests & Diagnostics", "8,500"),
        ("Nursing Charges", "4,000"),
    ]

    for desc, amount in items:
        y += 18
        page.insert_text((50, y), desc, fontsize=10)
        page.insert_text((430, y), amount, fontsize=10)

    # Total
    y += 25
    page.insert_text((50, y), "─" * 60, fontsize=10)
    y += 18
    page.insert_text((50, y), "Grand Total:", fontsize=12, fontname="helv")
    page.insert_text((410, y), "1,45,000", fontsize=12, fontname="helv")

    # Save to bytes
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Test 1: PyMuPDF Raw Text Extraction
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_raw_text_extraction(pdf_bytes: bytes) -> str:
    """Test Step 1: Raw text extraction via PyMuPDF."""
    print("\n" + "=" * 70)
    print("TEST 1: PyMuPDF Raw Text Extraction")
    print("=" * 70)

    from app.ai_agents.fraud.tools.pdf_extractor import get_raw_text

    raw_text = get_raw_text(pdf_bytes)
    print(f"✓ Extracted {len(raw_text)} characters of raw text")
    print(f"  Preview (first 500 chars):\n{raw_text[:500]}")

    assert len(raw_text) > 0, "Raw text should not be empty"
    print("✓ PASSED: Raw text extraction working")
    return raw_text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Test 2: Page Image Rendering
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_page_rendering(pdf_bytes: bytes) -> list[bytes]:
    """Test Step 2: PDF → PNG page rendering."""
    print("\n" + "=" * 70)
    print("TEST 2: PDF Page Rendering")
    print("=" * 70)

    from app.ai_agents.fraud.tools.pdf_extractor import get_page_images

    images = get_page_images(pdf_bytes)
    print(f"✓ Rendered {len(images)} page(s) as PNG images")
    for i, img in enumerate(images):
        print(f"  Page {i}: {len(img)} bytes")

    assert len(images) > 0, "Should render at least one page"
    print("✓ PASSED: Page rendering working")
    return images


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Test 3: Reconciliation Engine (with mock data)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_reconciliation_engine(raw_text: str):
    """Test the reconciliation checks with mock extracted data."""
    print("\n" + "=" * 70)
    print("TEST 3: Reconciliation Engine (Mock Data)")
    print("=" * 70)

    from app.ai_agents.fraud.tools.reconciliation import (
        literal_anchor_check,
        arithmetic_recalculation,
        shadow_comparison,
        calculate_integrity_score,
    )

    # ── 3a: Test with CONSISTENT data (should pass) ──
    print("\n--- 3a: Consistent data (should PASS all checks) ---")
    good_data = {
        "patient_name": "Rajesh Kumar",
        "hospital_name": "APOLLO HOSPITAL",
        "total_amount": 145000,
        "bill_number": "APL-2026-001234",
        "line_items": [
            {"item": "ICU Charges", "amount": 42000},
            {"item": "Surgery Charges", "amount": 60000},
            {"item": "Medicine & Consumables", "amount": 18500},
            {"item": "Doctor Consultation Fees", "amount": 12000},
            {"item": "Lab Tests & Diagnostics", "amount": 8500},
            {"item": "Nursing Charges", "amount": 4000},
        ],
    }

    literal = literal_anchor_check(good_data, raw_text)
    print(f"  Literal match: passed={literal['passed']}, "
          f"rate={literal['match_rate']:.2f} "
          f"({literal['matched_fields']}/{literal['total_fields']})")

    arith = arithmetic_recalculation(good_data)
    print(f"  Arithmetic: passed={arith['passed']}, "
          f"sum={arith['calculated_sum']}, total={arith['extracted_total']}, "
          f"diff={arith['difference_pct']}%")

    shadow = shadow_comparison(145000, 145000.0)
    print(f"  Shadow: passed={shadow['passed']}, diff={shadow['difference_pct']}%")

    checks_good = {"literal_match": literal, "arithmetic": arith, "shadow": shadow,
                   "coordinate": {"passed": True, "method": "skipped"}}
    score_good, flags_good = calculate_integrity_score(checks_good)
    print(f"  → Integrity score: {score_good}/100, flags: {flags_good}")
    assert score_good < 20, f"Good data should score low, got {score_good}"
    print("  ✓ PASSED: Consistent data scores clean")

    # ── 3b: Test with TAMPERED data (should fail) ──
    print("\n--- 3b: Tampered data (should FAIL checks) ---")
    bad_data = {
        "patient_name": "Rajesh Kumar",
        "hospital_name": "APOLLO HOSPITAL",
        "total_amount": 250000,  # Inflated total!
        "bill_number": "APL-2026-001234",
        "line_items": [
            {"item": "ICU Charges", "amount": 42000},
            {"item": "Surgery Charges", "amount": 60000},
            {"item": "Medicine & Consumables", "amount": 18500},
            {"item": "Doctor Consultation Fees", "amount": 12000},
            {"item": "Lab Tests & Diagnostics", "amount": 8500},
            {"item": "Nursing Charges", "amount": 4000},
        ],
    }

    literal_bad = literal_anchor_check(bad_data, raw_text)
    print(f"  Literal match: passed={literal_bad['passed']}, "
          f"rate={literal_bad['match_rate']:.2f}")
    if not literal_bad["passed"]:
        mismatched = [m["key"] for m in literal_bad["mismatched_fields"]]
        print(f"    Mismatched fields: {mismatched}")

    arith_bad = arithmetic_recalculation(bad_data)
    print(f"  Arithmetic: passed={arith_bad['passed']}, "
          f"sum={arith_bad['calculated_sum']}, total={arith_bad['extracted_total']}, "
          f"diff={arith_bad['difference_pct']}%")

    shadow_bad = shadow_comparison(250000, 145000.0)
    print(f"  Shadow: passed={shadow_bad['passed']}, diff={shadow_bad['difference_pct']}%")

    checks_bad = {"literal_match": literal_bad, "arithmetic": arith_bad,
                  "shadow": shadow_bad,
                  "coordinate": {"passed": False, "method": "gemini_coordinate",
                                 "coordinate_value": "145000", "primary_value": "250000"}}
    score_bad, flags_bad = calculate_integrity_score(checks_bad)
    print(f"  → Integrity score: {score_bad}/100")
    for f in flags_bad:
        print(f"    FLAG: {f}")
    assert score_bad > 50, f"Tampered data should score high, got {score_bad}"
    print("  ✓ PASSED: Tampered data correctly flagged")

    print("\n✓ ALL RECONCILIATION TESTS PASSED")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Test 4: Full Node 1 via LangGraph (requires GCP_API_KEY)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def test_full_node1(pdf_bytes: bytes):
    """Test the complete Node 1 execution via the LangGraph agent."""
    print("\n" + "=" * 70)
    print("TEST 4: Full Node 1 via LangGraph Agent")
    print("=" * 70)

    # Check if GCP_API_KEY is available
    try:
        from app.config import settings
        if not settings.GCP_API_KEY:
            print("⚠ SKIPPED: No GCP_API_KEY set — cannot run Gemini calls.")
            print("  Set GCP_API_KEY in .env to test the full pipeline.")
            return
    except Exception as exc:
        print(f"⚠ SKIPPED: Could not load settings ({exc}).")
        print("  Ensure .env exists with SECRET_KEY, ENCRYPTION_KEY, QR_SECRET_KEY, DATABASE_URL, GCP_API_KEY.")
        return

    from app.ai_agents.fraud.graph import run_fraud_agent

    print("Running fraud agent graph…")
    result = await run_fraud_agent(
        claim_id="test-claim-001",
        document_id="test-doc-001",
        document_bytes=pdf_bytes,
        document_type_code="HOSPITAL_BILL",
    )

    print(f"\n── Results ──")
    print(f"  Integrity Risk Score: {result.get('integrity_risk_score')}/100")
    print(f"  Final Fraud Score:    {result.get('final_fraud_score')}")
    print(f"  Risk Level:           {result.get('final_risk_level')}")

    flags = result.get("integrity_flags", [])
    if flags:
        print(f"  Flags ({len(flags)}):")
        for f in flags:
            print(f"    ⚑ {f}")
    else:
        print("  Flags: none (clean)")

    checks = result.get("integrity_checks", {})
    print(f"\n  Check details:")
    for check_name, check_data in checks.items():
        passed = check_data.get("passed", "?")
        skipped = check_data.get("skipped", False)
        status = "SKIP" if skipped else ("PASS" if passed else "FAIL")
        print(f"    {check_name}: {status}")

    node_results = result.get("node_results", {})
    print(f"\n  Node results: {json.dumps(node_results, indent=2, default=str)}")

    messages = result.get("messages", [])
    if messages:
        print(f"\n  Agent messages:")
        for msg in messages:
            print(f"    → {msg.content if hasattr(msg, 'content') else str(msg)}")

    print("\n✓ PASSED: Full Node 1 execution complete")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def main():
    print("╔══════════════════════════════════════════════════════╗")
    print("║  Node 1: Extraction Integrity — Test Suite          ║")
    print("╚══════════════════════════════════════════════════════╝")

    # Load PDF
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        pdf_path = sys.argv[1]
        print(f"\nLoading PDF from: {pdf_path}")
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        print(f"  Loaded {len(pdf_bytes)} bytes")
    else:
        print("\nNo PDF provided — creating synthetic test PDF…")
        pdf_bytes = create_test_pdf()
        print(f"  Created synthetic PDF ({len(pdf_bytes)} bytes)")
        # Save for inspection
        out_path = os.path.join(os.path.dirname(__file__), "test_hospital_bill.pdf")
        with open(out_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"  Saved to: {out_path}")

    # Run tests sequentially
    raw_text = test_raw_text_extraction(pdf_bytes)
    page_images = test_page_rendering(pdf_bytes)
    test_reconciliation_engine(raw_text)
    await test_full_node1(pdf_bytes)

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
