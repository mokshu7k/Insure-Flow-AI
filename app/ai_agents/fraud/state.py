"""
Fraud Detection Agent — LangGraph state definition.

The state flows through each fraud detection node sequentially.
Each node enriches the state with its findings.
"""
from __future__ import annotations

from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


def _merge_node_results(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    """Reducer that merges node_results dicts from parallel branches.

    When two parallel branches (e.g. Node 3 and Node 4) both write to
    ``node_results`` in the same step, LangGraph calls this reducer to
    combine them instead of raising InvalidUpdateError.
    """
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class FraudAgentState(TypedDict):
    """State passed through every node in the fraud detection agent graph.

    Each node reads ``document_bytes`` / ``extracted_data`` and appends
    its results to the corresponding key.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    claim_id: str
    document_id: str

    # ── Raw inputs (populated before graph invocation) ────────────────────────
    document_bytes: Optional[bytes]          # raw PDF/image bytes
    document_type_code: str                  # e.g. "HOSPITAL_BILL"
    existing_extracted_data: Optional[dict[str, Any]]  # Gemini extraction already on file

    # ── Multi-document context (for Node 2) ───────────────────────────────────
    # List of ALL documents on this claim:
    # [{"document_id": ..., "document_type_code": ..., "extracted_data": {...}}, ...]
    all_documents_data: Optional[list[dict[str, Any]]]
    # Policy metadata for date-window checks:
    # {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "sum_insured": 500000}
    policy_data: Optional[dict[str, Any]]

    # ── Node 1: Extraction Integrity results ──────────────────────────────────
    raw_text: Optional[str]                  # PyMuPDF raw text stream
    primary_extraction: Optional[dict[str, Any]]  # Gemini full JSON extraction
    shadow_total: Optional[float]            # Gemini shadow call — just the total
    integrity_checks: Optional[dict[str, Any]]    # per-check results
    integrity_risk_score: Optional[float]         # 0-100 composite score
    integrity_flags: Optional[list[str]]          # human-readable flag strings

    # ── Node 2: Cross-Document Consistency results ────────────────────────────
    consistency_checks: Optional[dict[str, Any]]
    consistency_risk_score: Optional[float]       # 0-100
    consistency_flags: Optional[list[str]]

    # ── Node 3: Document Intelligence results ─────────────────────────────────
    intelligence_checks: Optional[dict[str, Any]]
    intelligence_risk_score: Optional[float]      # 0-100
    intelligence_flags: Optional[list[str]]

    # ── Node 4: Image Forensics results (runs parallel to Nodes 1-3) ──────────
    forensics_checks: Optional[dict[str, Any]]
    forensics_risk_score: Optional[float]         # 0-100
    forensics_flags: Optional[list[str]]
    document_hashes: Optional[dict[str, Any]]     # pHash / aHash / dHash

    # ── Node 5: Document Content Fraud results (Gemini-powered) ───────────────
    content_fraud_checks: Optional[dict[str, Any]]
    content_fraud_risk_score: Optional[float]     # 0-100
    content_fraud_flags: Optional[list[str]]

    # ── Node 6: Behavioral & Statistical Risk results ─────────────────────────
    behavioral_checks: Optional[dict[str, Any]]
    behavioral_risk_score: Optional[float]        # 0-100
    behavioral_flags: Optional[list[str]]

    # ── Claim-level metadata (for Node 6 — populated by bridge) ───────────────
    # {"claim_amount", "claim_type", "sum_insured", "policy_start_date",
    #  "claim_created_at", "recent_claims_30d", "total_claim_amount_90d",
    #  "fraud_flag_count"}
    claim_metadata: Optional[dict[str, Any]]

    # ── Aggregate (filled after all nodes run) ────────────────────────────────
    node_results: Annotated[dict[str, Any], _merge_node_results]  # node_name → {score, flags, details}
    final_fraud_score: Optional[float]
    final_risk_level: Optional[str]

    # ── Enhanced aggregator outputs (Gemini synthesis) ────────────────────────
    manual_review_required: Optional[bool]
    manual_review_triggers: Optional[list[str]]
    risk_explanation: Optional[str]
    critical_signals: Optional[list[str]]

    # ── Messages (for LangGraph tooling / tracing) ────────────────────────────
    messages: Annotated[list, add_messages]
