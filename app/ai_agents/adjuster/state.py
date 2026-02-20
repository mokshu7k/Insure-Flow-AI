"""Adjuster agent state — TypedDict passed through all LangGraph nodes."""
from __future__ import annotations

from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AdjusterState(TypedDict):
    """State for the insurance adjuster LangGraph agent."""
    messages: Annotated[list, add_messages]
    claim_id: str                        # Claim being worked on
    adjuster_id: str                     # Requesting adjuster's user ID
    context: dict[str, Any]             # Accumulated tool results (populated lazily)
    report: Optional[str]               # Generated Markdown report (if requested)
