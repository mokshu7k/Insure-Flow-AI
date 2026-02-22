"""
Fraud Detection Agent — LangGraph pipeline.

Architecture (Nodes 1-6, Gemini-powered aggregator):

       ┌─→ Node 1 (Extraction) → Node 2 (Cross-Doc) → Node 3 (DocIntel) → Node 5 (ContentFraud/Gemini) ──┐
START ─┼─→ Node 4 (Image Forensics — parallel, pixel-level) ──────────────────────────────────────────────┼─→ aggregator(Gemini) → END
       └─→ Node 6 (Behavioral & Statistical Risk — parallel) ─────────────────────────────────────────────┘

Branch A (sequential):  Nodes 1→2→3→5  — extraction, cross-doc, ID checks, content fraud
Branch B (parallel):    Node 4         — image forensics (CV, no LLM)
Branch C (parallel):    Node 6         — behavioural / statistical (metadata, no LLM)
Aggregator:             Gemini-powered final scoring + risk synthesis + manual-review triggers
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from app.ai_agents.fraud.state import FraudAgentState
from app.ai_agents.fraud.nodes.extraction_integrity import extraction_integrity_node
from app.ai_agents.fraud.nodes.cross_document_consistency import cross_document_consistency_node
from app.ai_agents.fraud.nodes.document_intelligence import document_intelligence_node
from app.ai_agents.fraud.nodes.image_forensics import image_forensics_node
from app.ai_agents.fraud.nodes.document_content_fraud import document_content_fraud_node
from app.ai_agents.fraud.nodes.behavioral_risk import behavioral_risk_node

logger = logging.getLogger(__name__)


# ── Manual-review trigger patterns ────────────────────────────────────────────
# If ANY of these sub-strings appear in a flag → instant manual review.

_INSTANT_REVIEW_PATTERNS: list[tuple[str, str]] = [
    ("COPY_MOVE_DETECTED",    "Document tampering — copy-move regions detected"),
    ("PHASH_DUPLICATE",       "Document reuse — perceptual-hash duplicate"),
    ("CLAIM_BEFORE_POLICY",   "Temporal fraud — claim filed before policy start"),
    ("VERY_EARLY_CLAIM",      "Suspicious timing — very early claim after policy activation"),
    ("PRIOR_FRAUD_HISTORY",   "History — prior fraud flags on policyholder"),
    ("ARITHMETIC_MISMATCH",   "Financial — bill arithmetic inconsistency"),
    ("CONTENT_CRITICAL",      "AI analysis — critical content-fraud signal"),
]


# ── Aggregator node (Gemini-powered scoring + synthesis) ──────────────────────

async def aggregator_node(state: FraudAgentState, config: dict | None = None) -> dict[str, Any]:
    """Collect all node outputs, send them to Gemini which determines the
    final fraud score (instead of a static weighted formula), then apply
    deterministic manual-review triggers on top.

    Gemini receives each node's score, flags, and key check results and
    returns:
      - final_score (0-1)
      - risk_level (MINIMAL/LOW/MEDIUM/HIGH/VERY_HIGH)
      - risk_explanation (human-readable)
      - critical_signals
      - manual_review_recommended
    """
    node_results = state.get("node_results") or {}

    # ── 1. Collect all flags ──────────────────────────────────────────────
    all_flags: list[str] = []
    for node_data in node_results.values():
        if isinstance(node_data, dict):
            all_flags.extend(node_data.get("flags", []))

    # ── 2. Gemini-powered scoring + synthesis (single LLM call) ───────────
    try:
        from app.ai_agents.fraud.tools.gemini_content_analyzer import (
            generate_fraud_score_and_synthesis,
        )
        scoring = await generate_fraud_score_and_synthesis(
            node_results=node_results,
            all_flags=all_flags,
        )
    except Exception as exc:
        logger.error("Gemini scoring call failed in aggregator: %s", exc)
        scoring = None

    if scoring and "final_score" in scoring:
        final_score      = scoring["final_score"]
        risk_level       = scoring["risk_level"]
        risk_explanation  = scoring.get("risk_explanation", "")
        critical_signals  = scoring.get("critical_signals", all_flags[:5])
        manual_review     = scoring.get("manual_review_recommended", final_score >= 0.50)
    else:
        # Hard fallback — should never happen (the tool has its own fallback)
        final_score = 0.0
        risk_level  = "MINIMAL"
        risk_explanation = (
            f"Unable to generate AI-scored result. "
            f"{len(all_flags)} signal(s) from {len(node_results)} node(s)."
        )
        critical_signals = all_flags[:5]
        manual_review    = False

    # ── 3. Deterministic manual-review triggers (applied on top of AI) ────
    triggers: list[str] = []
    for pattern, reason in _INSTANT_REVIEW_PATTERNS:
        if any(pattern in f for f in all_flags):
            manual_review = True
            triggers.append(reason)

    if final_score >= 0.50 and not manual_review:
        manual_review = True
    if final_score >= 0.50:
        triggers.append(f"Aggregate risk score: {final_score:.2f} ({risk_level})")

    summary = (
        f"Fraud Agent complete — score={final_score:.4f} ({risk_level}), "
        f"nodes={len(node_results)}, flags={len(all_flags)}, "
        f"manual_review={manual_review}"
    )
    logger.info(summary)

    return {
        "final_fraud_score":      final_score,
        "final_risk_level":       risk_level,
        "manual_review_required": manual_review,
        "manual_review_triggers": triggers,
        "risk_explanation":       risk_explanation,
        "critical_signals":       critical_signals,
        "messages": [AIMessage(content=summary)],
    }


# ── Build the graph ──────────────────────────────────────────────────────────

def build_fraud_agent_graph():
    """Build and compile the 6-node fraud detection graph.

    Topology (3-branch fan-out → fan-in):

        START ─┬─→ extraction_integrity → cross_document_consistency
               │     → document_intelligence → document_content_fraud ──┐
               ├─→ image_forensics ─────────────────────────────────────┼─→ aggregator → END
               └─→ behavioral_risk ─────────────────────────────────────┘
    """
    graph = StateGraph(FraudAgentState)

    # Register all 6 detection nodes + aggregator
    graph.add_node("extraction_integrity",        extraction_integrity_node)
    graph.add_node("cross_document_consistency",   cross_document_consistency_node)
    graph.add_node("document_intelligence",        document_intelligence_node)
    graph.add_node("document_content_fraud",       document_content_fraud_node)
    graph.add_node("image_forensics",              image_forensics_node)
    graph.add_node("behavioral_risk",              behavioral_risk_node)
    graph.add_node("aggregator",                   aggregator_node)

    # Branch A: sequential  Nodes 1 → 2 → 3 → 5
    graph.add_edge(START, "extraction_integrity")
    graph.add_edge("extraction_integrity",        "cross_document_consistency")
    graph.add_edge("cross_document_consistency",   "document_intelligence")
    graph.add_edge("document_intelligence",        "document_content_fraud")
    graph.add_edge("document_content_fraud",       "aggregator")

    # Branch B: parallel  Node 4 (image forensics)
    graph.add_edge(START, "image_forensics")
    graph.add_edge("image_forensics", "aggregator")

    # Branch C: parallel  Node 6 (behavioural risk)
    graph.add_edge(START, "behavioral_risk")
    graph.add_edge("behavioral_risk", "aggregator")

    graph.add_edge("aggregator", END)

    return graph.compile()


# ── Singleton accessor ────────────────────────────────────────────────────────

_fraud_agent_graph = None


def get_fraud_agent_graph():
    """Get or create the compiled fraud agent graph."""
    global _fraud_agent_graph
    if _fraud_agent_graph is None:
        _fraud_agent_graph = build_fraud_agent_graph()
    return _fraud_agent_graph


async def run_fraud_agent(
    claim_id: str,
    document_id: str,
    document_bytes: bytes,
    document_type_code: str,
    existing_extracted_data: dict[str, Any] | None = None,
    all_documents_data: list[dict[str, Any]] | None = None,
    policy_data: dict[str, Any] | None = None,
    claim_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the full 6-node fraud agent on a single document.

    Args:
        claim_id: The claim being analysed.
        document_id: The specific document being checked.
        document_bytes: Raw PDF/image bytes.
        document_type_code: e.g. "HOSPITAL_BILL".
        existing_extracted_data: Previously extracted data (if any).
        all_documents_data: All documents on this claim (for cross-doc).
        policy_data: ``{"start_date", "end_date", "sum_insured"}``
        claim_metadata: Claim-level metadata for Node 6 (behavioural).
            ``{"claim_amount", "claim_type", "sum_insured",
              "policy_start_date", "claim_created_at",
              "recent_claims_30d", "total_claim_amount_90d",
              "fraud_flag_count"}``

    Returns:
        Full state dict including per-node risk scores, the final
        aggregated score, manual-review flags, and risk explanation.
    """
    graph = get_fraud_agent_graph()

    initial_state: dict[str, Any] = {
        "claim_id": claim_id,
        "document_id": document_id,
        "document_bytes": document_bytes,
        "document_type_code": document_type_code,
        "existing_extracted_data": existing_extracted_data,
        "all_documents_data": all_documents_data,
        "policy_data": policy_data,
        "claim_metadata": claim_metadata,
        "messages": [],
        # Node 1 outputs
        "raw_text": None,
        "primary_extraction": None,
        "shadow_total": None,
        "integrity_checks": None,
        "integrity_risk_score": None,
        "integrity_flags": None,
        # Node 2 outputs
        "consistency_checks": None,
        "consistency_risk_score": None,
        "consistency_flags": None,
        # Node 3 outputs
        "intelligence_checks": None,
        "intelligence_risk_score": None,
        "intelligence_flags": None,
        # Node 4 outputs
        "forensics_checks": None,
        "forensics_risk_score": None,
        "forensics_flags": None,
        "document_hashes": None,
        # Node 5 outputs
        "content_fraud_checks": None,
        "content_fraud_risk_score": None,
        "content_fraud_flags": None,
        # Node 6 outputs
        "behavioral_checks": None,
        "behavioral_risk_score": None,
        "behavioral_flags": None,
        # Aggregate
        "node_results": {},
        "final_fraud_score": None,
        "final_risk_level": None,
        "manual_review_required": None,
        "manual_review_triggers": None,
        "risk_explanation": None,
        "critical_signals": None,
    }

    result = await graph.ainvoke(initial_state)
    return result
