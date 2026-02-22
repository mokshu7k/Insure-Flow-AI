#!/usr/bin/env python
"""
Test script for Node 3: Document Intelligence.

Tests:
  1. PAN structural validation — valid, invalid, non-individual
  2. Aadhaar Verhoeff checksum — valid, invalid, masked
  3. Redaction integrity checker — clean, privacy violation, hallucination
  4. Greedy string matcher — found / not-found fields
  5. Full Node 3 execution (async) with synthetic state

All tests are offline — no LLM, no DB, no network.
"""
from __future__ import annotations

import asyncio
import sys
import os
import traceback

# ── project root on sys.path ──────────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

passed, failed, skipped = 0, 0, 0


def _report(name: str, ok: bool, detail: str = ""):
    global passed, failed
    tag = "PASS ✓" if ok else "FAIL ✗"
    print(f"  [{tag}] {name}" + (f"  ({detail})" if detail else ""))
    if ok:
        passed += 1
    else:
        failed += 1


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 1: PAN Structural Validation
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 1: PAN Validation ═══")
try:
    from app.ai_agents.fraud.tools.id_validator import validate_pan

    # 1a: Valid individual PAN
    result = validate_pan("ABCPD1234E")
    _report("Valid individual PAN", result["valid"] and result["status_code"] == "P")

    # 1b: Valid PAN but company (position 4 = C)
    result = validate_pan("ABCCD1234E", expect_individual=True)
    _report(
        "Company PAN flagged for individual claim",
        result["valid"] and "PAN_NOT_INDIVIDUAL" in result["flags"],
        f"flags={result['flags']}",
    )

    # 1c: Invalid format — wrong length
    result = validate_pan("ABC12")
    _report("Short PAN rejected", not result["valid"], f"flags={result['flags']}")

    # 1d: Invalid format — digits where letters expected
    result = validate_pan("12345A789B")
    _report("Bad format PAN rejected", not result["valid"], f"flags={result['flags']}")

    # 1e: Valid format, position 4 = H (HUF)
    result = validate_pan("ABCHD1234E", expect_individual=False)
    _report(
        "HUF PAN accepted when not expecting individual",
        result["valid"] and len(result["flags"]) == 0,
        f"status={result['status_meaning']}",
    )

except Exception as e:
    _report("PAN Validation", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 2: Aadhaar Verhoeff Checksum
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 2: Aadhaar Verhoeff Validation ═══")
try:
    from app.ai_agents.fraud.tools.id_validator import validate_aadhaar

    # 2a: Valid Aadhaar (checksum-correct number)
    # We use a known-good Verhoeff number: 499118665246
    # (you can compute: the Verhoeff check for "499118665246" should be 0)
    # Let's use a well-known test vector first — or we construct one.
    # Actually let's just test the algorithm with a number we can verify:
    # Verhoeff wiki example: 2363 is valid (checksum=0)
    # For a 12-digit Aadhaar, let's construct:
    # We'll test with a number and see if checksum logic works.

    # 2a: Masked Aadhaar — should pass (no checksum possible)
    result = validate_aadhaar("XXXX-XXXX-5246")
    _report(
        "Masked Aadhaar accepted",
        result["valid"] and result["is_masked"],
        f"masked={result['is_masked']}",
    )

    # 2b: Invalid start digit (0)
    result = validate_aadhaar("012345678901")
    _report(
        "Aadhaar starting with 0 rejected",
        not result["valid"],
        f"flags={result['flags']}",
    )

    # 2c: Invalid start digit (1)
    result = validate_aadhaar("123456789012")
    _report(
        "Aadhaar starting with 1 rejected",
        not result["valid"],
        f"flags={result['flags']}",
    )

    # 2d: Too short
    result = validate_aadhaar("2345 6789")
    _report(
        "Short Aadhaar rejected",
        not result["valid"],
        f"flags={result['flags']}",
    )

    # 2e: Valid-format 12-digit starting with 2+
    # Verhoeff check: need a number where _verhoeff_validate returns True.
    # The Verhoeff algorithm: for number "5" the check digit is 1, so "51" validates.
    # For "820382028203" — let's construct: we generate check digit for 11 digits.
    from app.ai_agents.fraud.tools.id_validator import _verhoeff_checksum, _VERHOEFF_INV

    # Build a valid 12-digit Aadhaar
    base_11 = "29947108610"  # starts with 2, 11 digits
    # Calculate check digit
    c = 0
    # We need checksum of "base_11" + check_digit = 0
    # Reverse iterate including the check digit at position 0
    # Easier: compute checksum of base_11, then find inverse
    c = 0
    for i, digit in enumerate(reversed(base_11)):
        from app.ai_agents.fraud.tools.id_validator import _VERHOEFF_D, _VERHOEFF_P
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][int(digit)]]
    check_digit = _VERHOEFF_INV[c]
    valid_aadhaar = base_11 + str(check_digit)

    result = validate_aadhaar(valid_aadhaar)
    _report(
        "Valid 12-digit Aadhaar (Verhoeff passes)",
        result["valid"] and result["checksum_passed"],
        f"aadhaar={valid_aadhaar}, checksum={result['checksum_passed']}",
    )

    # 2f: Tampered Aadhaar (change last digit)
    bad_last = int(valid_aadhaar[-1])
    tampered = valid_aadhaar[:-1] + str((bad_last + 1) % 10)
    result = validate_aadhaar(tampered)
    _report(
        "Tampered Aadhaar fails Verhoeff",
        not result["valid"] or not result["checksum_passed"],
        f"aadhaar={tampered}, checksum={result['checksum_passed']}",
    )

except Exception as e:
    _report("Aadhaar Verhoeff Validation", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 3: Redaction Integrity
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 3: Redaction Integrity ═══")
try:
    from app.ai_agents.fraud.tools.redaction_checker import check_redaction_integrity

    # 3a: Clean — Gemini has same digits as raw
    extracted_clean = {"aadhaar_number": "XXXX-XXXX-5246", "pan_number": "ABCPD1234E"}
    raw_clean = "Name: Rajesh Kumar\nAadhaar: XXXX-XXXX-5246\nPAN: ABCPD1234E"
    result = check_redaction_integrity(extracted_clean, raw_clean)
    _report("Clean extraction passes", result["passed"], f"checks={len(result['checks'])}")

    # 3b: Privacy violation — raw is masked but Gemini has full digits
    extracted_leak = {"aadhaar_number": "234567891234"}
    raw_masked = "Name: Rajesh Kumar\nAadhaar: XXXX-XXXX-1234"
    result = check_redaction_integrity(extracted_leak, raw_masked)
    has_privacy = len(result.get("privacy_violations", [])) > 0
    has_halluc = len(result.get("hallucinated_fields", [])) > 0
    _report(
        "Privacy violation / hallucination detected",
        has_privacy or has_halluc or not result["passed"],
        f"privacy={result.get('privacy_violations')}, halluc={result.get('hallucinated_fields')}",
    )

    # 3c: No sensitive fields — should pass
    extracted_empty = {"patient_name": "Rajesh Kumar"}
    raw_simple = "Patient: Rajesh Kumar"
    result = check_redaction_integrity(extracted_empty, raw_simple)
    _report("No sensitive fields → passes", result["passed"])

except Exception as e:
    _report("Redaction Integrity", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 4: Greedy String Matcher
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 4: Greedy String Matcher ═══")
try:
    from app.ai_agents.fraud.tools.redaction_checker import greedy_string_matcher

    # 4a: All fields found in raw text
    extracted = {
        "patient_name": "Rajesh Kumar",
        "hospital_name": "Apollo Hospitals",
        "doctor_name": "Dr. Anand Mehta",
    }
    raw_text = (
        "HOSPITAL BILL\n"
        "Apollo Hospitals, Jubilee Hills, Hyderabad\n"
        "Patient: Rajesh Kumar\n"
        "Treating Doctor: Dr. Anand Mehta\n"
        "Total: Rs. 45,000\n"
    )
    result = greedy_string_matcher(extracted, raw_text)
    _report(
        "All fields found in raw",
        result["passed"],
        f"match_rate={result['match_rate']:.0%}, found={result['found_count']}/{result['total_checked']}",
    )

    # 4b: Hallucinated field — name not in raw
    extracted_bad = {
        "patient_name": "Completely Different Name",
        "hospital_name": "Apollo Hospitals",
    }
    result = greedy_string_matcher(extracted_bad, raw_text)
    _report(
        "Hallucinated name flagged",
        not result["passed"] or len(result.get("not_found", [])) > 0,
        f"not_found={[nf['field'] for nf in result.get('not_found', [])]}",
    )

except Exception as e:
    _report("Greedy String Matcher", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 5: Full Node 3 Execution (async)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 5: Full Node 3 Execution ═══")
try:
    from app.ai_agents.fraud.nodes.document_intelligence import document_intelligence_node

    async def _run_node3():
        # Simulate state after Node 1 — with raw text and extraction
        state = {
            "claim_id": "CLM-TEST-003",
            "document_id": "doc-test-003",
            "document_bytes": None,
            "document_type_code": "HOSPITAL_BILL",
            "existing_extracted_data": None,
            "all_documents_data": None,
            "policy_data": None,
            "raw_text": (
                "HOSPITAL BILL\n"
                "Apollo Hospitals, Jubilee Hills\n"
                "Patient: Rajesh Kumar Sharma\n"
                "Aadhaar: XXXX-XXXX-5246\n"
                "PAN: ABCPD1234E\n"
                "Treating Doctor: Dr. Vikram Patel\n"
                "Diagnosis: Acute Appendicitis\n"
                "Total Amount: Rs. 75,000\n"
            ),
            "primary_extraction": {
                "patient_name": "Rajesh Kumar Sharma",
                "hospital_name": "Apollo Hospitals",
                "doctor_name": "Dr. Vikram Patel",
                "diagnosis": "Acute Appendicitis",
                "total_amount": "75000",
                "aadhaar_number": "XXXX-XXXX-5246",
                "pan_number": "ABCPD1234E",
            },
            "shadow_total": None,
            "integrity_checks": None,
            "integrity_risk_score": None,
            "integrity_flags": None,
            "consistency_checks": None,
            "consistency_risk_score": None,
            "consistency_flags": None,
            "intelligence_checks": None,
            "intelligence_risk_score": None,
            "intelligence_flags": None,
            "node_results": {},
            "final_fraud_score": None,
            "final_risk_level": None,
            "messages": [],
        }

        result = await document_intelligence_node(state)
        return result

    result = asyncio.run(_run_node3())
    score = result.get("intelligence_risk_score", -1)
    flags = result.get("intelligence_flags", [])
    checks = result.get("intelligence_checks", {})

    _report("Node 3 runs end-to-end", True, f"score={score}, flags={len(flags)}")

    # With clean data (PAN valid, Aadhaar masked, names in raw text), score should be low
    _report(
        "Clean data → low score",
        score < 30,
        f"score={score}",
    )

    # Check that PAN was validated
    pan_check = checks.get("pan_validation", {})
    _report(
        "PAN validated (ABCPD1234E)",
        pan_check.get("valid", False),
        f"status={pan_check.get('status_meaning')}",
    )

    # Check that Aadhaar was recognized as masked
    aadhaar_check = checks.get("aadhaar_validation", {})
    _report(
        "Aadhaar recognized as masked",
        aadhaar_check.get("is_masked", False),
        f"is_masked={aadhaar_check.get('is_masked')}",
    )

    # Greedy matcher should pass
    matcher_check = checks.get("greedy_matcher", {})
    _report(
        "Greedy matcher passes",
        matcher_check.get("passed", False),
        f"match_rate={matcher_check.get('match_rate', 0):.0%}",
    )

except Exception as e:
    _report("Full Node 3 Execution", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 6: Node 3 with Suspicious Data
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 6: Node 3 with Suspicious Data ═══")
try:
    from app.ai_agents.fraud.nodes.document_intelligence import document_intelligence_node

    async def _run_node3_suspicious():
        state = {
            "claim_id": "CLM-TEST-004",
            "document_id": "doc-suspicious-004",
            "document_type_code": "HOSPITAL_BILL",
            "existing_extracted_data": None,
            "all_documents_data": None,
            "policy_data": None,
            "document_bytes": None,
            "raw_text": (
                "HOSPITAL BILL\n"
                "City Hospital\n"
                "Patient: Amit Verma\n"
                "Aadhaar: XXXX-XXXX-7890\n"
                "PAN: ABCPD1234E\n"
                "Total: Rs. 50000\n"
            ),
            "primary_extraction": {
                # Hallucinated name — not in raw text
                "patient_name": "Completely Fake Patient Name",
                # Hospital name also hallucinated
                "hospital_name": "Super Specialty Medical Centre",
                # PAN is valid format but let's use an invalid one:
                "pan_number": "12345ABCDE",
                # Aadhaar — Gemini "saw through" the mask
                "aadhaar_number": "234567897890",
            },
            "shadow_total": None,
            "integrity_checks": None,
            "integrity_risk_score": None,
            "integrity_flags": None,
            "consistency_checks": None,
            "consistency_risk_score": None,
            "consistency_flags": None,
            "intelligence_checks": None,
            "intelligence_risk_score": None,
            "intelligence_flags": None,
            "node_results": {},
            "final_fraud_score": None,
            "final_risk_level": None,
            "messages": [],
        }

        result = await document_intelligence_node(state)
        return result

    result = asyncio.run(_run_node3_suspicious())
    score = result.get("intelligence_risk_score", 0)
    flags = result.get("intelligence_flags", [])

    _report(
        "Suspicious data → high score",
        score > 30,
        f"score={score}",
    )
    _report(
        "Multiple flags raised",
        len(flags) >= 2,
        f"total_flags={len(flags)}, flags={flags[:3]}",
    )

    # Check specific flags
    has_raw_mismatch = any("RAW_MISMATCH" in f for f in flags)
    has_pan_flag = any("PAN" in f for f in flags)

    _report(
        "Raw mismatch flag present",
        has_raw_mismatch,
        f"found={[f for f in flags if 'RAW_MISMATCH' in f][:2]}",
    )
    _report(
        "PAN invalid flag present",
        has_pan_flag,
        f"found={[f for f in flags if 'PAN' in f][:1]}",
    )

except Exception as e:
    _report("Node 3 with Suspicious Data", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'═' * 60}")
total = passed + failed
print(f"Results: {passed}/{total} passed, {failed} failed, {skipped} skipped")
if failed:
    print("⚠️  Some tests FAILED — see above for details.")
    sys.exit(1)
else:
    print("All tests passed!")
    sys.exit(0)
