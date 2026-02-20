"""LangGraph agent state definition."""
from __future__ import annotations

from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Graph state passed between all agent nodes.

    Flow:  supervisor → (route) → data_node → synthesizer
                               → synthesizer (skip data)
    """
    # ── Conversation memory (add_messages reducer = append, never overwrite) ──
    messages: Annotated[list, add_messages]

    # ── Identity ──────────────────────────────────────────────────────────────
    user_id: str
    session_id: str

    # ── Routing (set by supervisor) ───────────────────────────────────────────
    # "data_node"  → pass through data_node before synthesizer
    # "synthesizer" → skip data_node, go straight to synthesizer
    route: Optional[str]

    # ── Supervisor metadata ───────────────────────────────────────────────────
    supervisor_notes: Optional[str]     # brief reasoning / hints for data_node

    # ── Data accumulation (filled by data_node) ───────────────────────────────
    data_context: Optional[dict[str, Any]]   # merged tool results keyed by tool name

    # ── Misc ──────────────────────────────────────────────────────────────────
    intent: Optional[str]               # last node's intent label
    context: dict[str, Any]             # runtime objects (db session) — not persisted
    last_tool_result: Optional[dict[str, Any]]
