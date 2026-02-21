"""
Adjuster agent API — chat with the adjuster agent or generate a full claim report.
INSURER_ADMIN and CLAIM_ADJUSTER roles only.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/adjuster", tags=["adjuster-agent"])


def _content_str(content) -> str:
    """Normalise Gemini content — may be a string or a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
            else:
                parts.append(str(block))
        return "".join(parts).strip()
    return str(content)


class ChatRequest(BaseModel):
    claim_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    response: str
    report: str | None = None


class ReportResponse(BaseModel):
    report: str | None = None
    claim_id: str
    cached: bool
    generated_at: str | None = None


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
    reply = _content_str(last_ai.content) if last_ai else "No response generated."
    return ChatResponse(response=reply, report=result.get("report"))


@router.get("/report/{claim_id}", response_model=ReportResponse)
async def get_claim_report(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return cached report if it exists, otherwise return report=null."""
    from app.core.rbac import require_any_role
    from app.models.claim import Claim
    require_any_role(["INSURER_ADMIN", "CLAIM_ADJUSTER"])(current_user)
    claim = await db.get(Claim, uuid.UUID(claim_id))
    if claim and claim.ai_report:
        return ReportResponse(report=claim.ai_report, claim_id=claim_id, cached=True)
    return ReportResponse(report=None, claim_id=claim_id, cached=False)


@router.post("/report/{claim_id}", response_model=ReportResponse)
async def generate_claim_report(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate (or return cached) comprehensive Markdown claim report."""
    from app.core.rbac import require_any_role
    from app.models.claim import Claim
    from app.ai_agents.adjuster.tools import generate_report
    require_any_role(["INSURER_ADMIN", "CLAIM_ADJUSTER"])(current_user)

    # Return cached report if already generated
    claim = await db.get(Claim, uuid.UUID(claim_id))
    if claim and claim.ai_report:
        return ReportResponse(report=claim.ai_report, claim_id=claim_id, cached=True)

    try:
        result = await generate_report(
            claim_id=claim_id,
            db=db,
            adjuster_id=str(current_user.id),
        )
        if "error" in result:
            return ReportResponse(report=None, claim_id=claim_id, cached=False)

        report_text = result.get("report") or ""
        # Persist so subsequent calls are instant
        if claim and report_text:
            claim.ai_report = report_text
            db.add(claim)
            await db.commit()

        return ReportResponse(
            report=report_text,
            claim_id=claim_id,
            cached=False,
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
        )
    except Exception as exc:
        logger.error("generate_claim_report error: %s", exc, exc_info=True)
        return ReportResponse(report=None, claim_id=claim_id, cached=False)
