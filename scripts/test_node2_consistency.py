#!/usr/bin/env python
"""
Test script for Node 2: Cross-Document Consistency.

Tests:
  1. Name matcher tool — strict / fuzzy / mismatch
  2. Timeline validation — good / bad timelines
  3. Entity name cross-check across documents
  4. Policy window alignment
  5. Financial sum-of-parts
  6. Full node execution (async)

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
#  TEST 1: Name Matcher Tool
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 1: Name Matcher Tool ═══")
try:
    from app.ai_agents.fraud.tools.name_matcher import (
        strict_match, fuzzy_score, compare_names,
    )

    # 1a: Strict match with title stripping
    assert strict_match("Mr. Rajesh Kumar Sharma", "rajesh kumar sharma")
    _report("Strict match (title stripped)", True)

    # 1b: Strict match — different names
    assert not strict_match("Rajesh Kumar", "Suresh Kumar")
    _report("Strict match rejects different names", True)

    # 1c: Fuzzy score — word order swap
    score = fuzzy_score("Kumar Rajesh", "Rajesh Kumar")
    _report(f"Fuzzy score (word swap)", score > 0.60, f"score={score:.3f}")

    # 1d: Fuzzy score — abbreviation
    score = fuzzy_score("R.K. Sharma", "Rajesh Kumar Sharma")
    _report(f"Fuzzy score (abbreviation)", 0.4 < score < 0.9, f"score={score:.3f}")

    # 1e: compare_names — clear mismatch
    result = compare_names("Rajesh Kumar", "Priya Singh", "BillDoc", "LabDoc")
    _report(
        "compare_names (mismatch)",
        result["verdict"] == "IDENTITY_MISMATCH",
        f"verdict={result['verdict']}, fuzzy={result['fuzzy_score']:.2f}",
    )

    # 1f: compare_names — same name, different title
    result = compare_names("Shri Rajesh Sharma", "Mr. Rajesh Sharma", "A", "B")
    _report(
        "compare_names (title variant)",
        result["verdict"] == "MATCH",
        f"verdict={result['verdict']}, fuzzy={result['fuzzy_score']:.2f}",
    )

except Exception as e:
    _report("Name Matcher Tool", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 2: Timeline Sub-check (directly)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 2: Timeline Validation ═══")
try:
    from app.ai_agents.fraud.nodes.cross_document_consistency import (
        _check_timeline, _parse_date,
    )

    # 2a: Valid timeline — admission=2024-01-10, receipt=2024-01-12, discharge=2024-01-15
    good_docs = [
        {
            "document_id": "doc-bill-001",
            "document_type_code": "HOSPITAL_BILL",
            "promoted": {
                "admission_date": "10/01/2024",
                "discharge_date": "15/01/2024",
            },
        },
        {
            "document_id": "doc-lab-001",
            "document_type_code": "LAB_REPORT",
            "promoted": {
                "document_date": "12/01/2024",
            },
        },
    ]
    result = _check_timeline(good_docs)
    _report("Valid timeline passes", result["passed"], f"flags={result['flags']}")

    # 2b: Bad timeline — admission AFTER discharge
    bad_docs = [
        {
            "document_id": "doc-bill-002",
            "document_type_code": "HOSPITAL_BILL",
            "promoted": {
                "admission_date": "20/01/2024",  # AFTER discharge
                "discharge_date": "15/01/2024",
            },
        },
    ]
    result = _check_timeline(bad_docs)
    _report("Admission > discharge flagged", not result["passed"], f"flags={result['flags'][:1]}")

    # 2c: Document date after discharge (gap > 1 day)
    gap_docs = [
        {
            "document_id": "doc-bill-003",
            "document_type_code": "HOSPITAL_BILL",
            "promoted": {
                "admission_date": "10/01/2024",
                "discharge_date": "15/01/2024",
            },
        },
        {
            "document_id": "doc-receipt-003",
            "document_type_code": "PHARMACY_BILL",
            "promoted": {
                "document_date": "25/01/2024",  # 10 days after discharge
            },
        },
    ]
    result = _check_timeline(gap_docs)
    _report("Post-discharge gap flagged", not result["passed"], f"flags={result['flags'][:1]}")

except Exception as e:
    _report("Timeline Validation", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 3: Entity Names Across Documents
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 3: Entity Name Equality ═══")
try:
    from app.ai_agents.fraud.nodes.cross_document_consistency import _check_entity_names

    # 3a: Same patient across docs
    same_name_docs = [
        {
            "document_id": "doc-a",
            "document_type_code": "HOSPITAL_BILL",
            "promoted": {"patient_name": "Rajesh Kumar Sharma"},
        },
        {
            "document_id": "doc-b",
            "document_type_code": "LAB_REPORT",
            "promoted": {"patient_name": "Mr. Rajesh Kumar Sharma"},
        },
    ]
    result = _check_entity_names(same_name_docs)
    _report("Same patient name passes", result["passed"], f"comparisons={len(result['comparisons'])}")

    # 3b: Different patient name — fraud indicator
    diff_name_docs = [
        {
            "document_id": "doc-a",
            "document_type_code": "HOSPITAL_BILL",
            "promoted": {"patient_name": "Rajesh Kumar Sharma"},
        },
        {
            "document_id": "doc-b",
            "document_type_code": "LAB_REPORT",
            "promoted": {"patient_name": "Priya Singh"},
        },
    ]
    result = _check_entity_names(diff_name_docs)
    _report(
        "Different patient name flagged",
        not result["passed"],
        f"flags={result['flags'][:1]}",
    )

except Exception as e:
    _report("Entity Name Equality", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 4: Policy Window Alignment
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 4: Policy Window Alignment ═══")
try:
    from app.ai_agents.fraud.nodes.cross_document_consistency import _check_policy_window

    docs = [
        {
            "document_id": "doc-bill-100",
            "document_type_code": "HOSPITAL_BILL",
            "promoted": {
                "admission_date": "10/06/2024",
                "discharge_date": "15/06/2024",
            },
        },
    ]

    # 4a: Dates within policy window
    policy_ok = {"start_date": "2024-01-01", "end_date": "2024-12-31"}
    result = _check_policy_window(docs, policy_ok)
    _report("Dates within policy", result["passed"], f"flags={result['flags']}")

    # 4b: Dates BEFORE policy start
    policy_before = {"start_date": "2024-07-01", "end_date": "2024-12-31"}
    result = _check_policy_window(docs, policy_before)
    _report(
        "Dates before policy start flagged",
        not result["passed"],
        f"flags={result['flags'][:1]}",
    )

    # 4c: No policy data → skip gracefully
    result = _check_policy_window(docs, None)
    _report("No policy data → skipped", result.get("skipped", False))

except Exception as e:
    _report("Policy Window Alignment", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 5: Financial Sum-of-Parts
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 5: Financial Sum-of-Parts ═══")
try:
    from app.ai_agents.fraud.nodes.cross_document_consistency import _check_financial_sum

    # 5a: Receipts match grand total
    good_financial = [
        {
            "document_id": "bill-001",
            "document_type_code": "HOSPITAL_BILL",
            "promoted": {"total_amount": "50000"},
        },
        {
            "document_id": "pharma-001",
            "document_type_code": "PHARMACY_BILL",
            "promoted": {"total_amount": "8000"},
        },
        {
            "document_id": "lab-001",
            "document_type_code": "LAB_REPORT",
            "promoted": {"total_amount": "5000"},
        },
    ]
    result = _check_financial_sum(good_financial)
    _report(
        "Receipts under grand total",
        result["passed"],
        f"grand={result.get('grand_total')}, receipts={result.get('receipt_sum')}",
    )

    # 5b: Receipts WAY exceed grand total (inflation)
    inflated = [
        {
            "document_id": "bill-002",
            "document_type_code": "HOSPITAL_BILL",
            "promoted": {"total_amount": "50000"},
        },
        {
            "document_id": "pharma-002",
            "document_type_code": "PHARMACY_BILL",
            "promoted": {"total_amount": "40000"},
        },
        {
            "document_id": "lab-002",
            "document_type_code": "LAB_REPORT",
            "promoted": {"total_amount": "25000"},
        },
    ]
    result = _check_financial_sum(inflated)
    _report(
        "Inflated receipts flagged",
        not result["passed"],
        f"diff_pct={result.get('difference_pct')}%, flags={result['flags'][:1]}",
    )

except Exception as e:
    _report("Financial Sum-of-Parts", False, f"Exception: {e}")
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST 6: Full Node 2 Execution (async)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n═══ TEST 6: Full Node 2 Execution ═══")
try:
    from app.ai_agents.fraud.nodes.cross_document_consistency import (
        cross_document_consistency_node,
    )

    async def _run_node2():
        state = {
            "claim_id": "CLM-TEST-002",
            "document_id": "doc-primary-001",
            "document_bytes": None,
            "document_type_code": "HOSPITAL_BILL",
            "existing_extracted_data": None,
            "all_documents_data": [
                {
                    "document_id": "doc-bill-n2",
                    "document_type_code": "HOSPITAL_BILL",
                    "extracted_data": {
                        "patient_name": "Rajesh Kumar",
                        "admission_date": "10/01/2024",
                        "discharge_date": "15/01/2024",
                        "total_amount": "75,000",
                        "hospital_name": "Apollo Hospital",
                    },
                },
                {
                    "document_id": "doc-lab-n2",
                    "document_type_code": "LAB_REPORT",
                    "extracted_data": {
                        "patient_name": "Priya Singh",  # DIFFERENT NAME — should flag
                        "document_date": "12/01/2024",
                        "total_amount": "12,000",
                        "lab_name": "SRL Diagnostics",
                    },
                },
                {
                    "document_id": "doc-pharma-n2",
                    "document_type_code": "PHARMACY_BILL",
                    "extracted_data": {
                        "patient_name": "Rajesh Kumar",
                        "document_date": "14/01/2024",
                        "total_amount": "8,500",
                    },
                },
            ],
            "policy_data": {
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "sum_insured": 500000,
            },
            "raw_text": None,
            "primary_extraction": None,
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

        result = await cross_document_consistency_node(state)
        return result

    result = asyncio.run(_run_node2())
    score = result.get("consistency_risk_score", 0)
    flags = result.get("consistency_flags", [])
    has_name_flag = any("NAME" in f for f in flags)

    _report(
        "Node 2 runs end-to-end",
        True,
        f"score={score}, flags={len(flags)}",
    )
    _report(
        "Name mismatch detected",
        has_name_flag,
        f"found name-related flags: {[f for f in flags if 'NAME' in f][:2]}",
    )
    _report(
        "Score > 0 (issues found)",
        score > 0,
        f"consistency_risk_score={score}",
    )

except Exception as e:
    _report("Full Node 2 Execution", False, f"Exception: {e}")
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
