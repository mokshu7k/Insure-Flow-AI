#!/usr/bin/env python
"""
Test script for the Fraud Agent Bridge.

Tests the helper functions that assemble data from existing project
sources and feed it into the LangGraph fraud agent.

Tests:
  1. _decrypt_document_file — Fernet round-trip
  2. _build_all_documents_data — ORM-row-to-dict conversion
  3. _build_policy_data — verified_data snapshot extraction
  4. Full pipeline (synthetic) — encrypt → decrypt → agent run

All tests are offline — no DB, no network, no LLM.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import traceback
import uuid

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
#  TEST 1: Fernet encrypt → decrypt round-trip
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 1: Decrypt File Helper ═══")
try:
    from cryptography.fernet import Fernet

    # Generate a temporary key and override settings
    test_key = Fernet.generate_key()

    # Monkey-patch the module-level singleton
    import app.services.fraud_service as fs
    fs._fernet_instance = Fernet(test_key)

    # Create a synthetic PDF-like content and encrypt it
    original_bytes = b"%PDF-1.4\nThis is a fake PDF with line items.\nTotal: Rs. 50,000\n"
    encrypted = Fernet(test_key).encrypt(original_bytes)

    # Write to a temp file
    with tempfile.NamedTemporaryFile(suffix=".enc", delete=False) as f:
        f.write(encrypted)
        temp_path = f.name

    try:
        decrypted = fs._decrypt_document_file(temp_path)
        _report("Round-trip encrypt→decrypt", decrypted == original_bytes,
                f"original={len(original_bytes)}B, decrypted={len(decrypted)}B")
    finally:
        os.unlink(temp_path)

    # Test missing file raises NotFoundError
    try:
        fs._decrypt_document_file("/nonexistent/path/file.enc")
        _report("Missing file raises error", False, "No exception raised")
    except Exception as e:
        _report("Missing file raises error", "not found" in str(e).lower(),
                f"exception={type(e).__name__}")

except Exception as e:
    _report("Decrypt File Helper", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 2: Build all_documents_data from mock ORM objects
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 2: Build all_documents_data ═══")
try:
    from app.services.fraud_service import _build_all_documents_data
    from types import SimpleNamespace

    # Simulate ClaimDocument ORM rows
    doc1 = SimpleNamespace(
        id=uuid.uuid4(),
        document_type_code="HOSPITAL_BILL",
        extracted_data={"patient_name": "Rajesh Kumar", "total_amount": "75000"},
        ocr_status="COMPLETED",
    )
    doc2 = SimpleNamespace(
        id=uuid.uuid4(),
        document_type_code="LAB_REPORT",
        extracted_data={"patient_name": "Rajesh Kumar", "test_name": "CBC"},
        ocr_status="COMPLETED",
    )
    doc3_pending = SimpleNamespace(
        id=uuid.uuid4(),
        document_type_code="PRESCRIPTION",
        extracted_data=None,
        ocr_status="PENDING",  # should be excluded
    )

    result = _build_all_documents_data([doc1, doc2, doc3_pending])

    _report("Returns correct count", len(result) == 2,
            f"expected 2 (excl PENDING), got {len(result)}")
    _report("Contains extracted_data", result[0]["extracted_data"].get("patient_name") == "Rajesh Kumar")
    _report("Contains document_type_code", result[0]["document_type_code"] == "HOSPITAL_BILL")
    _report("Pending doc excluded", all(r["document_type_code"] != "PRESCRIPTION" for r in result))

except Exception as e:
    _report("Build all_documents_data", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 3: Build policy_data from mock Claim
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 3: Build policy_data ═══")
try:
    from app.services.fraud_service import _build_policy_data
    from types import SimpleNamespace

    # 3a: Claim with verified_data + policy_snapshot
    claim_ok = SimpleNamespace(
        verified_data={
            "policy_snapshot": {
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "sum_insured": 500000,
            }
        }
    )
    result = _build_policy_data(claim_ok)
    _report("Extracts policy_data", result is not None and result["sum_insured"] == 500000,
            f"result={result}")

    # 3b: Claim with no verified_data
    claim_none = SimpleNamespace(verified_data=None)
    result = _build_policy_data(claim_none)
    _report("No verified_data → None", result is None)

    # 3c: Claim with verified_data but no policy_snapshot key
    claim_empty = SimpleNamespace(verified_data={"other_key": "value"})
    result = _build_policy_data(claim_empty)
    _report("No policy_snapshot → None", result is None)

except Exception as e:
    _report("Build policy_data", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 4: Full Bridge Pipeline (synthetic — no DB)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 4: Full Bridge → Agent Pipeline ═══")
try:
    import fitz  # PyMuPDF
    from cryptography.fernet import Fernet as _F
    from app.ai_agents.fraud.graph import run_fraud_agent

    # Create a real (tiny) PDF in memory
    pdf_doc = fitz.open()
    page = pdf_doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "HOSPITAL BILL", fontname="helv", fontsize=16)
    page.insert_text((72, 130), "Patient: Rajesh Kumar Sharma", fontname="helv", fontsize=11)
    page.insert_text((72, 150), "Hospital: Apollo Hospitals", fontname="helv", fontsize=11)
    page.insert_text((72, 170), "Admission: 10/01/2024", fontname="helv", fontsize=11)
    page.insert_text((72, 190), "Discharge: 15/01/2024", fontname="helv", fontsize=11)
    page.insert_text((72, 210), "PAN: ABCPD1234E", fontname="helv", fontsize=11)
    page.insert_text((72, 230), "Aadhaar: XXXX-XXXX-5246", fontname="helv", fontsize=11)
    page.insert_text((72, 260), "Room Charges:    Rs. 30,000", fontname="helv", fontsize=11)
    page.insert_text((72, 280), "Surgery Charges: Rs. 45,000", fontname="helv", fontsize=11)
    page.insert_text((72, 310), "TOTAL:           Rs. 75,000", fontname="helv", fontsize=14)
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    # Encrypt → write to temp → decrypt (simulates the real path)
    test_key = _F.generate_key()
    fs._fernet_instance = _F(test_key)
    encrypted = _F(test_key).encrypt(pdf_bytes)
    with tempfile.NamedTemporaryFile(suffix=".enc", delete=False) as f:
        f.write(encrypted)
        enc_path = f.name

    try:
        # Decrypt (this is what the bridge does)
        decrypted_bytes = fs._decrypt_document_file(enc_path)
        _report("PDF bytes recovered", decrypted_bytes == pdf_bytes,
                f"size={len(decrypted_bytes)}B")

        # Now run the agent with those bytes
        async def _run():
            return await run_fraud_agent(
                claim_id="CLM-BRIDGE-TEST",
                document_id="DOC-BRIDGE-TEST",
                document_bytes=decrypted_bytes,
                document_type_code="HOSPITAL_BILL",
                existing_extracted_data={
                    "patient_name": "Rajesh Kumar Sharma",
                    "hospital_name": "Apollo Hospitals",
                    "total_amount": "75000",
                    "admission_date": "10/01/2024",
                    "discharge_date": "15/01/2024",
                    "pan_number": "ABCPD1234E",
                    "aadhaar_number": "XXXX-XXXX-5246",
                },
                all_documents_data=[
                    {
                        "document_id": "DOC-BRIDGE-TEST",
                        "document_type_code": "HOSPITAL_BILL",
                        "extracted_data": {
                            "patient_name": "Rajesh Kumar Sharma",
                            "hospital_name": "Apollo Hospitals",
                            "total_amount": "75000",
                            "admission_date": "10/01/2024",
                            "discharge_date": "15/01/2024",
                        },
                    },
                    {
                        "document_id": "DOC-LAB-001",
                        "document_type_code": "LAB_REPORT",
                        "extracted_data": {
                            "patient_name": "Rajesh Kumar Sharma",
                            "document_date": "12/01/2024",
                            "total_amount": "8000",
                        },
                    },
                ],
                policy_data={
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "sum_insured": 500000,
                },
            )

        result = asyncio.run(_run())

        # Verify all three nodes ran
        nr = result.get("node_results") or {}
        _report("Node 1 ran", "extraction_integrity" in nr,
                f"score={nr.get('extraction_integrity', {}).get('score')}")
        _report("Node 2 ran", "cross_document_consistency" in nr,
                f"score={nr.get('cross_document_consistency', {}).get('score')}")
        _report("Node 3 ran", "document_intelligence" in nr,
                f"score={nr.get('document_intelligence', {}).get('score')}")

        # Verify final aggregation
        _report("Final score exists", result.get("final_fraud_score") is not None,
                f"score={result.get('final_fraud_score')}")
        _report("Risk level exists", result.get("final_risk_level") is not None,
                f"level={result.get('final_risk_level')}")

    finally:
        os.unlink(enc_path)

except Exception as e:
    _report("Full Bridge Pipeline", False, f"Exception: {e}")
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
