"""
Adjuster LangGraph agent — single Gemini node with 6 read-only DB tools.
The agent can answer any question about a claim and generate a full report.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from app.ai_agents.adjuster.state import AdjusterState

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
            temperature=0.2,
        )
        return _llm
    except Exception as exc:
        logger.warning("Adjuster LLM unavailable: %s", exc)
        return None


# ── Tool wrappers (LangChain @tool for schema generation) ────────────────────

@tool
async def tool_get_full_claim(claim_id: str) -> str:
    """Get complete claim details: status, amount, type, description, timestamps."""
    return f"[TOOL: get_full_claim({claim_id})]"


@tool
async def tool_get_claimant_history(claim_id: str) -> str:
    """Get all past claims by the same claimant to identify patterns."""
    return f"[TOOL: get_claimant_history({claim_id})]"


@tool
async def tool_get_document_extractions(claim_id: str) -> str:
    """Get all uploaded documents and their Gemini-extracted structured data."""
    return f"[TOOL: get_document_extractions({claim_id})]"


@tool
async def tool_get_fraud_assessment(claim_id: str) -> str:
    """Get full fraud assessment: score, risk level, per-layer signals, AI explanation."""
    return f"[TOOL: get_fraud_assessment({claim_id})]"


@tool
async def tool_get_verification_report(claim_id: str) -> str:
    """Get AI verification report: cross-check of claim vs document data."""
    return f"[TOOL: get_verification_report({claim_id})]"


@tool
async def tool_generate_report(claim_id: str) -> str:
    """Generate a comprehensive claim processing report with recommendation and action items."""
    return f"[TOOL: generate_report({claim_id})]"


_TOOLS = [
    tool_get_full_claim,
    tool_get_claimant_history,
    tool_get_document_extractions,
    tool_get_fraud_assessment,
    tool_get_verification_report,
    tool_generate_report,
]

# Map tool name → real async function
from app.ai_agents.adjuster import tools as _tool_fns

_TOOL_DISPATCH: dict[str, Any] = {
    "tool_get_full_claim":           _tool_fns.get_full_claim,
    "tool_get_claimant_history":     _tool_fns.get_claimant_history,
    "tool_get_document_extractions": _tool_fns.get_document_extractions,
    "tool_get_fraud_assessment":     _tool_fns.get_fraud_assessment,
    "tool_get_verification_report":  _tool_fns.get_verification_report,
    "tool_generate_report":          _tool_fns.generate_report,
}


# ── Graph nodes ──────────────────────────────────────────────────────────────

async def gemini_node(state: AdjusterState, config: dict) -> dict:
    """Main Gemini node — decides which tools to call and generates a final reply."""
    try:
        llm = _get_llm()
        if not llm:
            return {
                "messages": [AIMessage(content="AI unavailable — check GCP_API_KEY.")],
            }

        llm_with_tools = llm.bind_tools(_TOOLS)

        claim_id = state.get("claim_id") or ""
        if claim_id:
            system_prompt = (
                "You are an expert insurance claim adjuster AI assistant. "
                f"You are helping process claim ID: {claim_id}. "
                "Use the available tools to pull claim data, documents, fraud assessments, and history. "
                "Always ground your answers in the data you retrieve. "
                "When asked to generate a report, use the generate_report tool."
            )
        else:
            system_prompt = (
                "You are an expert insurance claim adjuster AI assistant for InsureFlow. "
                "No specific claim is selected. You can answer general questions about insurance claims, "
                "policies, fraud patterns, and claim processing procedures. "
                "If the user asks about a specific claim, ask them to select it from the sidebar."
            )

        from langchain_core.messages import SystemMessage
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}
    except Exception as exc:
        logger.error("Adjuster gemini_node error: %s", exc)
        err_msg = AIMessage(content="I'm having trouble processing your request. Please try again shortly.")
        return {"messages": [err_msg]}


async def tool_execution_node(state: AdjusterState, config: dict) -> dict:
    """Execute all pending tool calls from the last Gemini message."""
    db = config["configurable"].get("db")
    adjuster_id = state["adjuster_id"]
    claim_id = state["claim_id"]

    last_message = state["messages"][-1]
    tool_messages = []

    for tc in last_message.tool_calls:
        fn = _TOOL_DISPATCH.get(tc["name"])
        if fn is None:
            result = {"error": f"Unknown tool: {tc['name']}"}
        else:
            try:
                result = await fn(claim_id, db=db, adjuster_id=adjuster_id)
            except Exception as exc:
                result = {"error": str(exc)}

        # If generate_report returned a report, capture it in state
        report = None
        if tc["name"] == "tool_generate_report" and "report" in result:
            report = result["report"]

        tool_messages.append(
            ToolMessage(content=str(result), tool_call_id=tc["id"])
        )

    update: dict[str, Any] = {"messages": tool_messages}
    if report is not None:
        update["report"] = report
    return update


def _should_continue(state: AdjusterState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


# ── Build graph ──────────────────────────────────────────────────────────────

def build_adjuster_graph():
    graph = StateGraph(AdjusterState)
    graph.add_node("gemini", gemini_node)
    graph.add_node("tools", tool_execution_node)

    graph.set_entry_point("gemini")
    graph.add_conditional_edges("gemini", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "gemini")

    return graph.compile()


_adjuster_graph = None


def get_adjuster_graph():
    global _adjuster_graph
    if _adjuster_graph is None:
        _adjuster_graph = build_adjuster_graph()
    return _adjuster_graph
