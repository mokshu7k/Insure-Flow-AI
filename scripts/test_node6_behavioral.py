#!/usr/bin/env python
"""
Test suite for Node 6: Behavioral & Statistical Risk + Full 6-Node Pipeline.

Covers the behavioral analyzer tool, the Node 6 wrapper, and an
end-to-end 6-node graph invocation (Gemini calls degrade gracefully
when GCP_API_KEY is absent).

Run:   .\venv\Scripts\python scripts\test_node6_behavioral.py
"""
from __future__ import annotations

import asyncio, io, os, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed = failed = skipped = 0


def report(name: str, ok: bool, detail: str = ""):
    global passed, failed
    tag = "\033[92mPASS \u2713\033[0m" if ok else "\033[91mFAIL \u2717\033[0m"
    passed += ok
    failed += not ok
    print(f"  [{tag}] {name}", f" ({detail})" if detail else "")


# ── helper: tiny valid JPEG for graph tests ──────────────────────────────────

def _make_tiny_jpeg(w: int = 8, h: int = 8) -> bytes:
    """Generate a minimal valid JPEG (white, w\u00d7h)."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (255, 255, 255)).save(buf, "JPEG")
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
#  TEST 1: Behavioral Analyzer Tool
# ═══════════════════════════════════════════════════════════════
def test_behavioral_analyzer():
    print("\n\u2550\u2550\u2550 TEST 1: Behavioral Analyzer Tool \u2550\u2550\u2550")
    from app.ai_agents.fraud.tools.behavioral_analyzer import analyze_behavioral_risk

    # 1a: Clean metadata
    clean = {
        "claim_amount": 50_000,
        "sum_insured": 500_000,
        "policy_start_date": "2024-01-01",
        "claim_created_at": "2025-06-15",
        "recent_claims_30d": 0,
        "total_claim_amount_90d": 0,
        "fraud_flag_count": 0,
    }
    r = analyze_behavioral_risk(clean)
    report("Clean metadata \u2192 score=0", r["risk_score"] == 0.0,
           f"score={r['risk_score']}, flags={r['flags']}")

    # 1b: Very early claim (15 days)
    early = {**clean, "policy_start_date": "2025-06-01", "claim_created_at": "2025-06-16"}
    r = analyze_behavioral_risk(early)
    has_very_early = any("VERY_EARLY_CLAIM" in f for f in r["flags"])
    report("15 days \u2192 VERY_EARLY_CLAIM", has_very_early,
           f"score={r['risk_score']}, flags={r['flags']}")

    # 1c: Early claim (60 days)
    somewhat = {**clean, "policy_start_date": "2025-04-15", "claim_created_at": "2025-06-14"}
    r = analyze_behavioral_risk(somewhat)
    has_early = any("EARLY_CLAIM" in f for f in r["flags"])
    report("60 days \u2192 EARLY_CLAIM", has_early,
           f"score={r['risk_score']}, flags={r['flags']}")

    # 1d: Claim BEFORE policy start
    before = {**clean, "policy_start_date": "2025-07-01", "claim_created_at": "2025-06-15"}
    r = analyze_behavioral_risk(before)
    has_before = any("CLAIM_BEFORE_POLICY" in f for f in r["flags"])
    report("Claim before policy \u2192 CLAIM_BEFORE_POLICY", has_before,
           f"score={r['risk_score']}, flags={r['flags']}")

    # 1e: High frequency
    freq = {**clean, "recent_claims_30d": 4}
    r = analyze_behavioral_risk(freq)
    has_freq = any("HIGH_CLAIM_FREQUENCY" in f for f in r["flags"])
    report("4 claims/30d \u2192 HIGH_CLAIM_FREQUENCY", has_freq,
           f"score={r['risk_score']}")

    # 1f: Moderate frequency
    freq2 = {**clean, "recent_claims_30d": 2}
    r = analyze_behavioral_risk(freq2)
    has_mod_freq = any("MODERATE_CLAIM_FREQUENCY" in f for f in r["flags"])
    report("2 claims/30d \u2192 MODERATE_CLAIM_FREQUENCY", has_mod_freq,
           f"score={r['risk_score']}")

    # 1g: High ratio (85%)
    ratio = {**clean, "claim_amount": 425_000, "sum_insured": 500_000}
    r = analyze_behavioral_risk(ratio)
    has_ratio = any("HIGH_CLAIM_RATIO" in f for f in r["flags"])
    report("85% ratio \u2192 HIGH_CLAIM_RATIO", has_ratio,
           f"score={r['risk_score']}")

    # 1h: Prior fraud flags
    prior = {**clean, "fraud_flag_count": 3}
    r = analyze_behavioral_risk(prior)
    has_prior = any("PRIOR_FRAUD_HISTORY" in f for f in r["flags"])
    report("Prior flags \u2192 PRIOR_FRAUD_HISTORY", has_prior,
           f"score={r['risk_score']}")

    # 1i: Very high 90d aggregate
    agg = {**clean, "total_claim_amount_90d": 450_000, "sum_insured": 500_000}
    r = analyze_behavioral_risk(agg)
    has_agg = any("VERY_HIGH_AGGREGATE" in f for f in r["flags"])
    report("90% aggregate \u2192 VERY_HIGH_AGGREGATE", has_agg,
           f"score={r['risk_score']}")

    # 1j: Multiple combined factors
    risky = {
        "claim_amount": 425_000,
        "sum_insured": 500_000,
        "policy_start_date": "2025-06-01",
        "claim_created_at": "2025-06-10",
        "recent_claims_30d": 4,
        "total_claim_amount_90d": 450_000,
        "fraud_flag_count": 2,
    }
    r = analyze_behavioral_risk(risky)
    report("Multiple factors \u2192 high score", r["risk_score"] >= 80,
           f"score={r['risk_score']}, flag_count={len(r['flags'])}")

    # 1k: Missing metadata
    r = analyze_behavioral_risk({})
    report("Empty metadata \u2192 score=0, no crash", r["risk_score"] == 0.0,
           f"flags={r['flags']}")

    # 1l: None metadata
    r = analyze_behavioral_risk(None)
    report("None metadata \u2192 graceful skip", r["risk_score"] == 0.0)


# ═══════════════════════════════════════════════════════════════
#  TEST 2: Node 6 Wrapper
# ═══════════════════════════════════════════════════════════════
def test_node6_execution():
    print("\n\u2550\u2550\u2550 TEST 2: Node 6 Execution \u2550\u2550\u2550")
    from app.ai_agents.fraud.nodes.behavioral_risk import behavioral_risk_node

    # 2a: No metadata \u2192 skipped
    state = {"claim_id": "c-1", "claim_metadata": None}
    r = asyncio.run(behavioral_risk_node(state))
    has_skip = any("SKIPPED" in f for f in r["behavioral_flags"])
    report("No metadata \u2192 SKIPPED", has_skip, f"flags={r['behavioral_flags']}")

    # 2b: Clean metadata
    state["claim_metadata"] = {
        "claim_amount": 50_000,
        "sum_insured": 500_000,
        "policy_start_date": "2024-01-01",
        "claim_created_at": "2025-06-15",
        "recent_claims_30d": 0,
        "total_claim_amount_90d": 0,
        "fraud_flag_count": 0,
    }
    r = asyncio.run(behavioral_risk_node(state))
    report("Clean \u2192 score=0", r["behavioral_risk_score"] == 0.0,
           f"score={r['behavioral_risk_score']}")

    # 2c: Risky metadata
    state["claim_metadata"] = {
        "claim_amount": 450_000,
        "sum_insured": 500_000,
        "policy_start_date": "2025-06-01",
        "claim_created_at": "2025-06-10",
        "recent_claims_30d": 5,
        "total_claim_amount_90d": 480_000,
        "fraud_flag_count": 2,
    }
    r = asyncio.run(behavioral_risk_node(state))
    report("Risky \u2192 high score", r["behavioral_risk_score"] >= 70,
           f"score={r['behavioral_risk_score']}, flag_count={len(r['behavioral_flags'])}")

    # 2d: node_results populated
    nr = r["node_results"]
    report("node_results has behavioral_risk",
           "behavioral_risk" in nr and nr["behavioral_risk"]["score"] >= 70,
           f"score={nr.get('behavioral_risk', {}).get('score')}")


# ═══════════════════════════════════════════════════════════════
#  TEST 3: Full 6-Node Pipeline
# ═══════════════════════════════════════════════════════════════
def test_full_pipeline():
    print("\n\u2550\u2550\u2550 TEST 3: Full 6-Node Pipeline \u2550\u2550\u2550")
    import app.ai_agents.fraud.graph as graph_mod

    # Force rebuild after our code changes
    graph_mod._fraud_agent_graph = None
    compiled = graph_mod.build_fraud_agent_graph()

    jpeg_bytes = _make_tiny_jpeg()

    initial_state = {
        "claim_id": "pipe-test",
        "document_id": "doc-test",
        "document_bytes": jpeg_bytes,
        "document_type_code": "HOSPITAL_BILL",
        "existing_extracted_data": {
            "line_items": [
                {"description": "Room", "amount": 5000},
                {"description": "Fee",  "amount": 3000},
            ],
            "total_amount": 8000,
            "diagnosis": "Acute appendicitis",
        },
        "all_documents_data": None,
        "policy_data": None,
        "claim_metadata": {
            "claim_amount": 8000,
            "sum_insured": 500_000,
            "policy_start_date": "2024-01-01",
            "claim_created_at": "2025-06-15",
            "recent_claims_30d": 0,
            "total_claim_amount_90d": 0,
            "fraud_flag_count": 0,
        },
        "messages": [],
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
        "forensics_checks": None,
        "forensics_risk_score": None,
        "forensics_flags": None,
        "document_hashes": None,
        "content_fraud_checks": None,
        "content_fraud_risk_score": None,
        "content_fraud_flags": None,
        "behavioral_checks": None,
        "behavioral_risk_score": None,
        "behavioral_flags": None,
        "node_results": {},
        "final_fraud_score": None,
        "final_risk_level": None,
        "manual_review_required": None,
        "manual_review_triggers": None,
        "risk_explanation": None,
        "critical_signals": None,
    }

    state = asyncio.run(compiled.ainvoke(initial_state))
    nr = state.get("node_results", {})
    nodes_found = sorted(nr.keys())

    # Check all 6 nodes ran
    for name in [
        "extraction_integrity",
        "cross_document_consistency",
        "document_intelligence",
        "image_forensics",
        "document_content_fraud",
        "behavioral_risk",
    ]:
        present = name in nodes_found
        score = nr.get(name, {}).get("score", "N/A")
        report(f"{name} ran", present, f"score={score}")

    # Final score exists
    final = state.get("final_fraud_score")
    level = state.get("final_risk_level")
    report("Final score computed", final is not None,
           f"score={final}, level={level}")

    # Manual review fields populated
    mr = state.get("manual_review_required")
    report("manual_review_required populated", mr is not None,
           f"manual_review={mr}")

    # Risk explanation exists
    expl = state.get("risk_explanation")
    report("risk_explanation present",
           expl is not None and len(str(expl)) > 0,
           f"length={len(str(expl)) if expl else 0}")

    # All 6 nodes in results
    report("All 6 nodes in results", len(nodes_found) == 6,
           f"nodes={nodes_found}")


# ═══════════════════════════════════════════════════════════════
#  TEST 4: Manual Review Triggers
# ═══════════════════════════════════════════════════════════════
def test_manual_review():
    print("\n\u2550\u2550\u2550 TEST 4: Manual Review Triggers \u2550\u2550\u2550")
    from app.ai_agents.fraud.graph import aggregator_node

    # 4a: Score-based trigger (\u2265 0.50)
    state = {
        "node_results": {
            "document_content_fraud": {"score": 80, "flags": ["ARITHMETIC_MISMATCH: test"], "details": {}},
            "behavioral_risk": {"score": 90, "flags": ["VERY_EARLY_CLAIM: test"], "details": {}},
        },
    }
    r = asyncio.run(aggregator_node(state))
    report("High score \u2192 manual review", r["manual_review_required"] is True,
           f"triggers={r['manual_review_triggers']}")

    # 4b: Pattern-based trigger (COPY_MOVE_DETECTED)
    state = {
        "node_results": {
            "image_forensics": {
                "score": 30,
                "flags": ["COPY_MOVE_DETECTED: 500 blocks"],
                "details": {},
            },
        },
    }
    r = asyncio.run(aggregator_node(state))
    has_copy_move_trigger = any("tampering" in t.lower() for t in r.get("manual_review_triggers", []))
    report("COPY_MOVE \u2192 instant review",
           r["manual_review_required"] is True and has_copy_move_trigger,
           f"triggers={r['manual_review_triggers']}")

    # 4c: Clean \u2192 no review
    state = {
        "node_results": {
            "extraction_integrity": {"score": 0, "flags": [], "details": {}},
            "behavioral_risk": {"score": 0, "flags": [], "details": {}},
        },
    }
    r = asyncio.run(aggregator_node(state))
    report("Clean \u2192 no manual review", r["manual_review_required"] is False,
           f"score={r['final_fraud_score']}")

    # 4d: Skipped nodes excluded from weighted average
    state = {
        "node_results": {
            "extraction_integrity": {"score": 0, "flags": [], "details": {}},
            "image_forensics": {"score": 100, "flags": ["test"], "details": {}},
            "behavioral_risk": {"score": 0, "flags": [], "details": {"skipped": True}},
        },
    }
    r = asyncio.run(aggregator_node(state))
    # behavioral_risk should be skipped from average
    # Only extraction (0*0.20) + forensics (100*0.15) counted
    # weighted = 0.15, total_weight = 0.35, score = 0.15/0.35 ≈ 0.4286
    expected_approx = 0.15 / 0.35
    report("Skipped node excluded from average",
           abs(r["final_fraud_score"] - expected_approx) < 0.01,
           f"score={r['final_fraud_score']:.4f}, expected~{expected_approx:.4f}")


# ═══════════════════════════════════════════════════════════════
#  TEST 5: Bridge Integration
# ═══════════════════════════════════════════════════════════════
def test_bridge_integration():
    print("\n\u2550\u2550\u2550 TEST 5: Bridge Integration \u2550\u2550\u2550")
    import inspect
    from app.services import fraud_service
    src = inspect.getsource(fraud_service)

    report("Bridge assembles claim_metadata", "claim_metadata" in src)
    report("Bridge passes claim_metadata to agent",
           "claim_metadata=claim_metadata" in src)
    report("Config version = agent_v2_6nodes",
           "agent_v2_6nodes" in src)

    # Weight map has all 6 nodes
    for node in [
        "extraction_integrity", "cross_document_consistency",
        "document_intelligence", "image_forensics",
        "document_content_fraud", "behavioral_risk",
    ]:
        report(f"  Weight map: {node}", f'"{node}"' in src)

    # Persists manual review info
    report("Persists manual_review_triggers",
           "manual_review_triggers" in src)
    report("Persists risk_explanation",
           "risk_explanation" in src)


# ═══════════════════════════════════════════════════════════════
#  RUN ALL
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n  Run:   .\\venv\\Scripts\\python scripts\\test_node6_behavioral.py")
    print("=" * 60)
    print("  Node 6: Behavioral Risk + Pipeline \u2014 Test Suite")
    print("=" * 60)

    test_behavioral_analyzer()
    test_node6_execution()
    test_full_pipeline()
    test_manual_review()
    test_bridge_integration()

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{passed + failed} passed, "
          f"{failed} failed, {skipped} skipped")
    if failed == 0:
        print("All tests passed!")
    else:
        print(f"FAILURES: {failed}")
    print()
