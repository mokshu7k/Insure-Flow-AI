"""
InsureFlow AI Conversational Agent — powered entirely by Gemini.

Architecture:
  - Single Gemini node with native LangChain tool calling (no heuristic routing).
  - Gemini decides WHICH tool to call based on the conversation.
  - Tools are real DB-backed functions injected via state context.
  - LangGraph is used purely for state persistence between turns, NOT routing.

Flow:
  START → gemini_agent (loops until Gemini stops calling tools) → END
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from app.ai_agents.agent.state import AgentState

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are InsureFlow AI, an intelligent insurance claims assistant.
You have access to tools that can look up real data for the user.
Always use the tools when the user asks about specific claims, fraud, or their account.
Be professional, concise, and empathetic.
When referencing monetary amounts, use Indian Rupee formatting (₹).
If you need a claim ID and the user hasn't provided one, ask them for it."""


def _build_tools(db, user_id: str) -> list:
    """Build LangChain-compatible tool definitions bound to the current DB session."""
    from langchain_core.tools import tool

    @tool
    async def get_claim_status(claim_id: str) -> str:
        """Get the current status, type, and amount of a specific insurance claim by its UUID."""
        from app.ai_agents.agent.tools import get_claim_status as _fn
        result = await _fn(claim_id, db=db, user_id=user_id)
        return json.dumps(result)

    @tool
    async def list_my_claims() -> str:
        """List the user's most recent insurance claims with status and amount."""
        from app.ai_agents.agent.tools import list_user_claims as _fn
        result = await _fn(db=db, user_id=user_id)
        return json.dumps(result)

    @tool
    async def explain_fraud_assessment(claim_id: str) -> str:
        """Get a detailed explanation of the fraud assessment for a specific claim."""
        from app.ai_agents.agent.tools import get_fraud_explanation as _fn
        result = await _fn(claim_id, db=db, user_id=user_id)
        return json.dumps(result)

    @tool
    async def check_consent() -> str:
        """Check whether the user has given valid data processing consent."""
        from app.ai_agents.agent.tools import check_consent_status as _fn
        result = await _fn(db=db, user_id=user_id)
        return json.dumps(result)

    return [get_claim_status, list_my_claims, explain_fraud_assessment, check_consent]


def _get_llm(tools: list):
    """Get a Gemini LLM instance bound with the provided tools."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    from app.config import settings

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.GCP_API_KEY,
        temperature=0.3,
    )
    return llm.bind_tools(tools)


async def gemini_agent_node(state: AgentState) -> dict:
    """
    Single Gemini node. Gemini reads the full conversation history,
    decides whether to call a tool or reply directly.
    If it calls a tool, we execute it and loop back (via LangGraph).
    """
    db = state["context"].get("db")
    user_id = state["user_id"]

    tools = _build_tools(db, user_id)
    tool_map = {t.name: t for t in tools}

    try:
        llm_with_tools = _get_llm(tools)

        # Build message list: system + conversation history
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])

        response: AIMessage = await llm_with_tools.ainvoke(messages)

        # If Gemini called tools, execute them
        if response.tool_calls:
            tool_results = []
            for tc in response.tool_calls:
                tool_fn = tool_map.get(tc["name"])
                if tool_fn:
                    try:
                        tool_output = await tool_fn.ainvoke(tc["args"])
                    except Exception as e:
                        tool_output = json.dumps({"error": str(e)})
                else:
                    tool_output = json.dumps({"error": f"Unknown tool: {tc['name']}"})

                tool_results.append(ToolMessage(
                    content=tool_output,
                    tool_call_id=tc["id"],
                ))

            # Feed tool results back and get final response
            messages_with_results = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"]) + [response] + tool_results
            final_response: AIMessage = await llm_with_tools.ainvoke(messages_with_results)

            return {
                "messages": [response] + tool_results + [final_response],
                "intent": "tool_call",
            }
        else:
            # Direct reply — no tool needed
            return {
                "messages": [response],
                "intent": "direct_reply",
            }

    except Exception as exc:
        logger.error("Gemini agent error: %s", exc)
        err_msg = AIMessage(content="I'm having trouble connecting right now. Please try again shortly.")
        return {"messages": [err_msg], "intent": "error"}


def build_graph() -> StateGraph:
    """
    Simple 2-node graph: START → gemini_agent → END.
    All intelligence lives in Gemini — LangGraph just manages state.
    """
    graph = StateGraph(AgentState)
    graph.add_node("gemini_agent", gemini_agent_node)
    graph.add_edge(START, "gemini_agent")
    graph.add_edge("gemini_agent", END)
    return graph.compile()


# Singleton compiled graph (loaded at import time)
agent_graph = build_graph()
