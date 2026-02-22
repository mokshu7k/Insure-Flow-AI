"""Auditor agent state — passed through all LangGraph nodes."""
from __future__ import annotations

from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AuditorState(TypedDict):
    """State for the autonomous insurance auditor LangGraph agent."""
    messages: Annotated[list, add_messages]
    run_id: str                              # e.g. "audit-2026-02-22T02:00:00"
    raw_signals: dict[str, Any]             # tool_name -> raw output dict
    final_findings: list[dict[str, Any]]    # structured findings after Gemini analysis
    summary_narrative: Optional[str]        # executive summary Gemini writes
    errors: dict[str, str]                  # tool_name -> error message
    analysis_complete: bool
