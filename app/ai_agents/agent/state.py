"""LangGraph agent state definition."""
from __future__ import annotations

from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Graph state passed between all agent nodes."""
    messages: Annotated[list, add_messages]
    user_id: str
    session_id: str
    intent: Optional[str]
    context: dict[str, Any]   # loaded from DB between turns
    last_tool_result: Optional[dict[str, Any]]
