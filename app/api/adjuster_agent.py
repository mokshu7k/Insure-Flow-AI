"""
Adjuster agent API — chat with the adjuster agent or generate a full claim report.
INSURER_ADMIN and CLAIM_ADJUSTER roles only.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/adjuster", tags=["adjuster-agent"])


class ChatRequest(BaseModel):
    claim_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    response: str
    report: str | None = None   # Populated when generate_report tool was invoked


@router.post("/chat", response_model=ChatResponse)
async def adjuster_chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chat with the adjuster AI agent about a specific claim."""
    from app.core.rbac import require_any_role
    require_any_role(["INSURER_ADMIN", "CLAIM_ADJUSTER"])(current_user)

    from app.ai_agents.adjuster.graph import get_adjuster_graph
    from app.ai_agents.adjuster.state import AdjusterState
    from langchain_core.messages import HumanMessage

    graph = get_adjuster_graph()

    initial_state: AdjusterState = {
        "messages": [HumanMessage(content=payload.message)],
        "claim_id": payload.claim_id or "",
        "adjuster_id": str(current_user.id),
        "context": {},
        "report": None,
    }

    config = {"configurable": {"db": db}}
    result = await graph.ainvoke(initial_state, config=config)

    last_ai = next(
        (m for m in reversed(result["messages"]) if hasattr(m, "content") and not getattr(m, "tool_calls", None)),
        None,
    )
    reply = last_ai.content if last_ai else "No response generated."
    return ChatResponse(response=reply, report=result.get("report"))


@router.post("/report/{claim_id}")
async def generate_claim_report(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a comprehensive Markdown claim report for adjuster review."""
    import logging
    from datetime import datetime, timezone
    from app.core.rbac import require_any_role
    require_any_role(["INSURER_ADMIN", "CLAIM_ADJUSTER"])(current_user)

    from app.ai_agents.adjuster.tools import generate_report

    try:
        result = await generate_report(
            claim_id=claim_id,
            db=db,
            adjuster_id=str(current_user.id),
        )
        if "error" in result:
            return result
        return {
            "report": result.get("report", ""),
            "claim_id": claim_id,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }
    except Exception as exc:
        logging.getLogger(__name__).error("generate_claim_report error: %s", exc, exc_info=True)
        return {"error": f"Report generation failed: {exc}"}
