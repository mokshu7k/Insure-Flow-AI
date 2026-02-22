#!/usr/bin/env python
"""
Test suite for Node 5: Document Content Fraud (Gemini-Powered).

Tests deterministic arithmetic / GST validation and the full node
execution.  Gemini calls will gracefully degrade if no GCP_API_KEY.

Run:   .\venv\Scripts\python scripts\test_node5_content_fraud.py
"""
from __future__ import annotations

import asyncio, os, sys, textwrap, io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed = failed = skipped = 0


def report(name: str, ok: bool, detail: str = ""):
    global passed, failed
    tag = "\033[92mPASS \u2713\033[0m" if ok else "\033[91mFAIL \u2717\033[0m"
    passed += ok
    failed += not ok
    print(f"  [{tag}] {name}", f" ({detail})" if detail else "")


# ═══════════════════════════════════════════════════════════════
#  TEST 1: Arithmetic Validator
# ═══════════════════════════════════════════════════════════════
def test_arithmetic():
    print("\n\u2550\u2550\u2550 TEST 1: Arithmetic Validator \u2550\u2550\u2550")
    from app.ai_agents.fraud.tools.arithmetic_gst_validator import validate_arithmetic

    # 1a: Clean bill (items sum correctly)
    clean = {
        "line_items": [
            {"description": "Room charges", "quantity": 3, "rate": 2000, "amount": 6000},
            {"description": "Doctor fee",   "quantity": 1, "rate": 3000, "amount": 3000},
            {"description": "Medicines",    "quantity": 1, "rate": 1500, "amount": 1500},
        ],
        "subtotal": 10500,
        "total_amount": 10500,
    }
    r = validate_arithmetic(clean)
    report("Clean bill \u2192 no flags", len(r["flags"]) == 0, f"flags={r['flags']}")

    # 1b: Mismatched total
    bad_total = {
        "line_items": [
            {"description": "Room", "amount": 6000},
            {"description": "Fee",  "amount": 3000},
        ],
        "total_amount": 12000,  # should be 9000
    }
    r = validate_arithmetic(bad_total)
    has_mismatch = any("ARITHMETIC_MISMATCH" in f for f in r["flags"])
    report("Mismatched total \u2192 ARITHMETIC_MISMATCH", has_mismatch, f"flags={r['flags']}")

    # 1c: Line item qty\u00d7rate \u2260 amount
    bad_item = {
        "line_items": [
            {"description": "Room", "quantity": 3, "rate": 2000, "amount": 7000},
        ],
        "total_amount": 7000,
    }
    r = validate_arithmetic(bad_item)
    has_line_err = any("LINE_ITEM_MATH_ERROR" in f for f in r["flags"])
    report("Line item math error", has_line_err, f"flags={r['flags']}")

    # 1d: Total decomposition error
    bad_decomp = {
        "line_items": [],
        "subtotal": 10000,
        "gst_amount": 1800,
        "total_amount": 13000,  # should be 11800
    }
    r = validate_arithmetic(bad_decomp)
    has_decomp = any("TOTAL_DECOMPOSITION_ERROR" in f for f in r["flags"])
    report("Total decomposition error", has_decomp, f"flags={r['flags']}")

    # 1e: No line items \u2192 no crash
    r = validate_arithmetic({"total_amount": 5000})
    report("No line items \u2192 no crash", r is not None, f"flags={r['flags']}")


# ═══════════════════════════════════════════════════════════════
#  TEST 2: GST Validator
# ═══════════════════════════════════════════════════════════════
def test_gst():
    print("\n\u2550\u2550\u2550 TEST 2: GST Validator \u2550\u2550\u2550")
    from app.ai_agents.fraud.tools.arithmetic_gst_validator import validate_gst

    # 2a: Standard 18% GST
    r = validate_gst({"subtotal": 10000, "gst_amount": 1800})
    no_anom = not any("GST_RATE_ANOMALY" in f for f in r["flags"])
    report("Standard 18% GST \u2192 no anomaly", no_anom,
           f"rate={r.get('computed_gst_rate')}, flags={r['flags']}")

    # 2b: Non-standard rate (15%)
    r = validate_gst({"subtotal": 10000, "gst_amount": 1500})
    has_anom = any("GST_RATE_ANOMALY" in f for f in r["flags"])
    report("15% GST \u2192 anomaly flagged", has_anom,
           f"rate={r.get('computed_gst_rate')}, flags={r['flags']}")

    # 2c: CGST/SGST mismatch
    r = validate_gst({"subtotal": 10000, "cgst": 500, "sgst": 900})
    has_mismatch = any("CGST_SGST_MISMATCH" in f for f in r["flags"])
    report("CGST \u2260 SGST \u2192 flagged", has_mismatch, f"flags={r['flags']}")

    # 2d: Invalid GSTIN
    r = validate_gst({"gstin": "INVALID123"})
    has_gstin = any("GSTIN_FORMAT_INVALID" in f for f in r["flags"])
    report("Invalid GSTIN \u2192 flagged", has_gstin, f"flags={r['flags']}")

    # 2e: Valid GSTIN (15-char)
    r = validate_gst({"gstin": "27AABCU9603R1ZM"})
    no_gstin = not any("GSTIN_FORMAT_INVALID" in f for f in r["flags"])
    report("Valid GSTIN \u2192 no flag", no_gstin, f"flags={r['flags']}")

    # 2f: Missing data \u2192 skipped
    r = validate_gst({})
    report("Missing data \u2192 skipped", r.get("skipped") is True,
           f"reason={r.get('reason')}")


# ═══════════════════════════════════════════════════════════════
#  TEST 3: Score Calculation
# ═══════════════════════════════════════════════════════════════
def test_score_calc():
    print("\n\u2550\u2550\u2550 TEST 3: Content Fraud Score Calculation \u2550\u2550\u2550")
    from app.ai_agents.fraud.nodes.document_content_fraud import (
        _calculate_content_fraud_score,
    )

    # 3a: All clean
    score, flags = _calculate_content_fraud_score([], [], [], 0)
    report("All clean \u2192 score=0", score == 0.0, f"score={score}")

    # 3b: Arithmetic mismatch only
    score, flags = _calculate_content_fraud_score(
        ["ARITHMETIC_MISMATCH: ..."], [], [], 0,
    )
    report("Arithmetic mismatch \u2192 score~70", 60 <= score <= 80,
           f"score={score}")

    # 3c: Multiple deterministic issues
    score, flags = _calculate_content_fraud_score(
        ["ARITHMETIC_MISMATCH: ...", "LINE_ITEM_MATH_ERROR: ..."],
        ["GST_RATE_ANOMALY: ..."],
        [],
        0,
    )
    report("Multiple issues \u2192 high score", score >= 70, f"score={score}")

    # 3d: With Gemini signals (blended)
    signals = [
        {"signal": "Oncology drug for mild fever", "severity": "HIGH", "category": "MEDICAL"},
    ]
    score, flags = _calculate_content_fraud_score([], [], signals, 60)
    report("Gemini HIGH signal \u2192 blended score", 40 <= score <= 85,
           f"score={score}")

    # 3e: CRITICAL signal
    signals = [
        {"signal": "Phantom charges detected", "severity": "CRITICAL", "category": "PRICING"},
    ]
    score, flags = _calculate_content_fraud_score([], [], signals, 90)
    has_crit = any("CONTENT_CRITICAL" in f for f in flags)
    report("CRITICAL signal \u2192 flag present", has_crit, f"flags={flags}")


# ═══════════════════════════════════════════════════════════════
#  TEST 4: Full Node 5 Execution
# ═══════════════════════════════════════════════════════════════
def test_node5_execution():
    print("\n\u2550\u2550\u2550 TEST 4: Full Node 5 Execution \u2550\u2550\u2550")
    from app.ai_agents.fraud.nodes.document_content_fraud import (
        document_content_fraud_node,
    )

    # 4a: No extracted data \u2192 skipped
    state = {
        "claim_id": "test-claim",
        "document_id": "test-doc",
        "document_type_code": "HOSPITAL_BILL",
        "primary_extraction": None,
        "existing_extracted_data": None,
        "all_documents_data": None,
    }
    result = asyncio.run(document_content_fraud_node(state))
    has_skip = any("SKIPPED" in f for f in result["content_fraud_flags"])
    report("No extracted data \u2192 SKIPPED", has_skip,
           f"flags={result['content_fraud_flags']}")

    # 4b: Clean hospital bill
    clean_bill = {
        "line_items": [
            {"description": "Room (3 days)", "quantity": 3, "rate": 2000, "amount": 6000},
            {"description": "Doctor fee", "quantity": 1, "rate": 5000, "amount": 5000},
        ],
        "subtotal": 11000,
        "gst_amount": 1980,
        "total_amount": 12980,
        "diagnosis": "Acute appendicitis",
    }
    state["existing_extracted_data"] = clean_bill
    result = asyncio.run(document_content_fraud_node(state))
    checks = result["content_fraud_checks"]
    report("Clean bill \u2192 arithmetic OK",
           "arithmetic" in checks and len(checks["arithmetic"].get("flags", [])) == 0,
           f"arith_flags={checks.get('arithmetic', {}).get('flags', [])}")

    # 4c: Bill with mismatched total
    bad_bill = {
        "line_items": [
            {"description": "Room", "amount": 6000},
            {"description": "Fee",  "amount": 5000},
        ],
        "total_amount": 15000,  # should be 11000
    }
    state["existing_extracted_data"] = bad_bill
    state["primary_extraction"] = None
    result = asyncio.run(document_content_fraud_node(state))
    has_arith = any("ARITHMETIC_MISMATCH" in f for f in result["content_fraud_flags"])
    report("Bad total \u2192 ARITHMETIC_MISMATCH", has_arith,
           f"score={result['content_fraud_risk_score']}, flags_count={len(result['content_fraud_flags'])}")

    # 4d: node_results populated
    nr = result["node_results"]
    report("node_results has document_content_fraud",
           "document_content_fraud" in nr,
           f"score={nr.get('document_content_fraud', {}).get('score')}")

    # 4e: Test with primary_extraction (should prefer it over existing)
    state["primary_extraction"] = clean_bill
    state["existing_extracted_data"] = bad_bill  # should be ignored
    result = asyncio.run(document_content_fraud_node(state))
    # Should use clean_bill, so no arithmetic mismatch
    no_arith = not any("ARITHMETIC_MISMATCH" in f for f in result["content_fraud_flags"])
    report("primary_extraction preferred over existing", no_arith,
           f"flags={result['content_fraud_flags'][:2]}")


# ═══════════════════════════════════════════════════════════════
#  TEST 5: Gemini Content Analyzer (graceful degradation)
# ═══════════════════════════════════════════════════════════════
def test_gemini_content():
    print("\n\u2550\u2550\u2550 TEST 5: Gemini Content Analyzer (degradation) \u2550\u2550\u2550")
    from app.ai_agents.fraud.tools.gemini_content_analyzer import (
        analyze_document_content,
        generate_risk_synthesis,
    )

    # Without a valid GCP key these skip; with a key, they should return valid results
    result = asyncio.run(analyze_document_content(
        "HOSPITAL_BILL", {"diagnosis": "test", "total_amount": 10000},
    ))
    is_valid = (
        result.get("skipped") is True
        or ("signals" in result and "risk_score" in result)
    )
    report("Content analysis \u2192 skipped OR valid result", is_valid,
           f"skipped={result.get('skipped')}, risk_score={result.get('risk_score')}")

    # Risk synthesis also degrades
    result = asyncio.run(generate_risk_synthesis(
        node_results={"test": {"score": 50, "flags": ["a"]}},
        all_flags=["a"],
        final_score=0.5,
        risk_level="MEDIUM",
    ))
    report("Synthesis degrades gracefully",
           "risk_explanation" in result,
           f"explanation={result.get('risk_explanation', '')[:60]}")


# ═══════════════════════════════════════════════════════════════
#  TEST 6: Diagnosis Consistency (multi-doc)
# ═══════════════════════════════════════════════════════════════
def test_diagnosis_consistency():
    print("\n\u2550\u2550\u2550 TEST 6: Multi-Document Diagnosis Consistency \u2550\u2550\u2550")
    from app.ai_agents.fraud.nodes.document_content_fraud import (
        document_content_fraud_node,
    )

    state = {
        "claim_id": "test-claim",
        "document_id": "test-doc",
        "document_type_code": "HOSPITAL_BILL",
        "primary_extraction": None,
        "existing_extracted_data": {"diagnosis": "Acute appendicitis", "total_amount": 50000},
        "all_documents_data": [
            {"document_id": "d1", "document_type_code": "HOSPITAL_BILL",
             "extracted_data": {"diagnosis": "Acute appendicitis"}},
            {"document_id": "d2", "document_type_code": "DISCHARGE_SUMMARY",
             "extracted_data": {"diagnosis": "Chronic migraine"}},  # different!
        ],
    }
    result = asyncio.run(document_content_fraud_node(state))
    checks = result["content_fraud_checks"]
    has_diag = checks.get("diagnosis_consistency", {}).get("consistent") is False
    report("Different diagnoses \u2192 inconsistent",
           has_diag, f"diag={checks.get('diagnosis_consistency')}")

    # Consistent diagnoses
    state["all_documents_data"] = [
        {"document_id": "d1", "document_type_code": "HOSPITAL_BILL",
         "extracted_data": {"diagnosis": "Acute appendicitis"}},
        {"document_id": "d2", "document_type_code": "DISCHARGE_SUMMARY",
         "extracted_data": {"diagnosis": "Acute appendicitis"}},
    ]
    result = asyncio.run(document_content_fraud_node(state))
    checks = result["content_fraud_checks"]
    is_consistent = checks.get("diagnosis_consistency", {}).get("consistent") is True
    report("Same diagnoses \u2192 consistent", is_consistent,
           f"diag={checks.get('diagnosis_consistency')}")


# ═══════════════════════════════════════════════════════════════
#  TEST 7: Bridge Weight Map
# ═══════════════════════════════════════════════════════════════
def test_bridge_weights():
    print("\n\u2550\u2550\u2550 TEST 7: Bridge Weight Map & Config \u2550\u2550\u2550")
    import inspect
    from app.services import fraud_service
    src = inspect.getsource(fraud_service)

    report("Bridge has document_content_fraud weight",
           "document_content_fraud" in src)
    report("Bridge has behavioral_risk weight",
           "behavioral_risk" in src)
    report("Config version = agent_v2_6nodes",
           "agent_v2_6nodes" in src)
    report("claim_metadata assembled in bridge",
           "claim_metadata" in src)
    report("Weight 0.25 for content fraud",
           '"document_content_fraud":      0.25' in src or
           '"document_content_fraud": 0.25' in src)


# ═══════════════════════════════════════════════════════════════
#  RUN ALL
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n  Run:   .\\venv\\Scripts\\python scripts\\test_node5_content_fraud.py")
    print("=" * 60)
    print("  Node 5: Document Content Fraud \u2014 Test Suite")
    print("=" * 60)

    test_arithmetic()
    test_gst()
    test_score_calc()
    test_node5_execution()
    test_gemini_content()
    test_diagnosis_consistency()
    test_bridge_weights()

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{passed + failed} passed, "
          f"{failed} failed, {skipped} skipped")
    if failed == 0:
        print("All tests passed!")
    else:
        print(f"FAILURES: {failed}")
    print()
