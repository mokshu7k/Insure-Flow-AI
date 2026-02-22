"""
Auditor LangGraph agent — 3-node autonomous sweep.

Nodes
-----
data_collection_node  — runs all 10 DB signal tools concurrently
analysis_node         — sends raw signals to Gemini for reasoning + classification
persistence_node      — saves AuditRun + AuditFindings to DB (immutable, append-only)
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

from app.ai_agents.auditor.state import AuditorState

logger = logging.getLogger(__name__)

_llm = None


def _get_llm():
    global _llm
    if _llm is not None:
        return _llm
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from app.config import settings
        _llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GCP_API_KEY,
            temperature=0.1,
        )
        return _llm
    except Exception as exc:
        logger.warning("Auditor LLM unavailable: %s", exc)
        return None


# ── Node 1: Data Collection ───────────────────────────────────────────────────

async def data_collection_node(state: AuditorState, config) -> dict:
    """Run all 10 signal tools concurrently and collect raw results."""
    db = config["configurable"]["db"]
    from app.ai_agents.auditor import tools as t

    signal_tasks = {
        "adjuster_provider_collusion": t.check_adjuster_provider_collusion(db=db),
        "provider_overbilling":        t.check_provider_overbilling(db=db),
        "underpayment_pattern":        t.check_underpayment_pattern(db=db),
        "high_fraud_score_approved":   t.check_high_fraud_score_approved(db=db),
        "abnormal_settlement_speed":   t.check_abnormal_settlement_speed(db=db),
        "settlement_discrepancy":      t.check_settlement_discrepancy(db=db),
        "claim_amount_gap":            t.check_claim_amount_gap(db=db),
        "provider_cluster_activity":   t.check_provider_cluster_activity(db=db),
        "user_claim_surge":            t.check_user_claim_surge(db=db),
        "document_integrity":          t.check_document_integrity(db=db),
    }

    results = await asyncio.gather(*signal_tasks.values(), return_exceptions=True)

    raw_signals: dict[str, Any] = {}
    errors: dict[str, str] = {}

    for key, result in zip(signal_tasks.keys(), results):
        if isinstance(result, Exception):
            errors[key] = str(result)
            raw_signals[key] = {}
        elif isinstance(result, dict) and "error" in result:
            errors[key] = result["error"]
            raw_signals[key] = {}
        else:
            raw_signals[key] = result

    logger.info(
        "[Auditor] Data collection done. %d tools ok, %d errors.",
        len(raw_signals) - len(errors),
        len(errors),
    )

    return {
        "raw_signals": raw_signals,
        "errors": errors,
        "messages": [
            HumanMessage(content=f"[AuditRun:{state['run_id']}] Data collection complete.")
        ],
    }


# ── Node 2: Gemini Analysis ───────────────────────────────────────────────────

_ANALYSIS_SYSTEM_PROMPT = """You are a senior insurance fraud auditor reviewing automated signals collected across the entire claims platform.

Your task: analyze each signal category and produce a JSON array of structured findings.

Each finding must be a JSON object with these exact keys:
- finding_type: one of [ADJUSTER_PROVIDER_COLLUSION, PROVIDER_OVERBILLING, UNDERPAYMENT_PATTERN, HIGH_FRAUD_SCORE_APPROVED, ABNORMAL_SETTLEMENT_SPEED, SETTLEMENT_AMOUNT_DISCREPANCY, CLAIM_AMOUNT_GAP, PROVIDER_CLUSTER_ACTIVITY, USER_CLAIM_SURGE, DOCUMENT_INTEGRITY_FLAGS]
- severity: one of [CRITICAL, HIGH, MEDIUM, LOW]
- entity_type: one of [CLAIM, PROVIDER, ADJUSTER, USER, CLUSTER]
- entity_id: the primary UUID/ID string of the most suspicious entity
- supporting_entity_ids: list of other related ID strings
- description: 1-2 sentence factual summary of what was found
- gemini_narrative: 3-5 sentence detailed reasoning explaining why this is suspicious
- recommended_action: concrete investigative next step for a human auditor
- evidence: the relevant subset of raw data that supports this finding (as a dict)

Rules:
1. Only produce a finding if the signal data actually contains data rows. Empty arrays = no finding.
2. For HIGH_FRAUD_SCORE_APPROVED, produce one finding per claim row — each is independently severe.
3. For ABNORMAL_SETTLEMENT_SPEED, produce one finding per claim row.
4. For all other signal types, produce one finding summarizing the worst-offending entity.
5. Severity guide: CRITICAL = clear fraud/collusion evidence; HIGH = strong pattern; MEDIUM = notable anomaly; LOW = worth monitoring.
6. Return ONLY a valid JSON array. No markdown fences, no prose outside the array.

After the JSON array, on a new line starting with exactly "SUMMARY:", write a 3-5 sentence executive summary of the entire sweep."""


async def analysis_node(state: AuditorState, config) -> dict:
    """Send raw signals to Gemini for reasoning, classification, and narrative writing."""
    llm = _get_llm()
    if not llm:
        logger.warning("[Auditor] LLM unavailable — zero findings produced.")
        return {
            "final_findings": [],
            "summary_narrative": "LLM unavailable. Raw signals collected but not analyzed.",
            "analysis_complete": True,
        }

    raw_signals = state.get("raw_signals", {})

    # Only send non-empty signal buckets to save tokens
    non_empty = {
        k: v for k, v in raw_signals.items()
        if v and isinstance(v, dict) and any(
            vals for vals in v.values() if isinstance(vals, list) and vals
        )
    }

    if not non_empty:
        return {
            "final_findings": [],
            "summary_narrative": "No suspicious signals detected in this sweep. System appears healthy.",
            "analysis_complete": True,
        }

    signal_payload = json.dumps(non_empty, indent=2, default=str)

    prompt = (
        f"{_ANALYSIS_SYSTEM_PROMPT}\n\n"
        f"=== RAW AUDIT SIGNALS ===\n{signal_payload}\n\n"
        "Produce the findings JSON array now:"
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content
        if isinstance(content, list):
            content = "".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in content
            )

        # Split findings JSON and executive summary
        summary_narrative: str | None = None
        if "SUMMARY:" in content:
            parts = content.split("SUMMARY:", 1)
            json_part = parts[0].strip()
            summary_narrative = parts[1].strip()
        else:
            json_part = content.strip()

        # Strip any markdown code fences Gemini might add
        if "```" in json_part:
            for fence in ["```json", "```"]:
                if fence in json_part:
                    json_part = json_part.split(fence, 1)[-1]
                    json_part = json_part.rsplit("```", 1)[0]
                    break

        final_findings: list[dict] = json.loads(json_part.strip())
        logger.info("[Auditor] Gemini produced %d findings.", len(final_findings))

    except Exception as exc:
        logger.error("[Auditor] Analysis node error: %s", exc)
        final_findings = []
        summary_narrative = f"Analysis failed: {exc}"

    return {
        "final_findings": final_findings,
        "summary_narrative": summary_narrative,
        "analysis_complete": True,
    }


# ── Node 3: Persistence ───────────────────────────────────────────────────────

async def persistence_node(state: AuditorState, config) -> dict:
    """Persist AuditRun + AuditFinding rows in a single transaction."""
    db = config["configurable"]["db"]
    from app.ai_agents.auditor.persistence import AuditPersistenceService

    svc = AuditPersistenceService(db)
    try:
        await svc.save_run(
            run_id=state["run_id"],
            findings=state.get("final_findings", []),
            raw_signals=state.get("raw_signals", {}),
            summary_narrative=state.get("summary_narrative"),
            errors=state.get("errors", {}),
        )
        logger.info(
            "[Auditor] Persisted run %s with %d findings.",
            state["run_id"],
            len(state.get("final_findings", [])),
        )
    except Exception as exc:
        logger.error("[Auditor] Persistence failed: %s", exc)

    return {}


# ── Build graph ───────────────────────────────────────────────────────────────

def build_auditor_graph():
    """Construct and compile the auditor StateGraph."""
    graph = StateGraph(AuditorState)

    graph.add_node("data_collection", data_collection_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("persistence", persistence_node)

    graph.set_entry_point("data_collection")
    graph.add_edge("data_collection", "analysis")
    graph.add_edge("analysis", "persistence")
    graph.add_edge("persistence", END)

    return graph.compile()


_compiled_graph = None


def get_auditor_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_auditor_graph()
    return _compiled_graph


async def run_audit_sweep(run_id: str, db) -> dict:
    """
    Entry point for scripts/run_audit.py.
    Returns a summary dict with findings_count, summary, and errors.
    """
    graph = get_auditor_graph()
    initial_state: AuditorState = {
        "messages": [],
        "run_id": run_id,
        "raw_signals": {},
        "final_findings": [],
        "summary_narrative": None,
        "errors": {},
        "analysis_complete": False,
    }
    config = {"configurable": {"db": db}}
    final_state = await graph.ainvoke(initial_state, config=config)
    return {
        "run_id": run_id,
        "findings_count": len(final_state.get("final_findings", [])),
        "summary": final_state.get("summary_narrative"),
        "errors": final_state.get("errors", {}),
    }
