"""
Node 6: Behavioral & Statistical Risk — Claim Metadata Analysis.

Purely deterministic analysis of claim-level metadata patterns.
No document content needed, no LLM calls. Runs in **parallel** with
the document-analysis chain from START.

Checks:
  1. Claim timing   (days since policy activation)
  2. Claim frequency (30-day window)
  3. Claim-to-sum-insured ratio
  4. 90-day aggregate claims
  5. Prior fraud flag history
"""
from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.messages import AIMessage

from app.ai_agents.fraud.state import FraudAgentState

logger = logging.getLogger(__name__)


async def behavioral_risk_node(
    state: FraudAgentState,
    config: dict | None = None,
) -> dict[str, Any]:
    """LangGraph node — behavioural & statistical risk analysis.

    Reads
    -----
    state["claim_metadata"]

    Writes
    ------
    behavioral_checks, behavioral_risk_score, behavioral_flags,
    node_results (partial), messages
    """
    from app.ai_agents.fraud.tools.behavioral_analyzer import (
        analyze_behavioral_risk,
    )

    claim_id = state.get("claim_id", "unknown")
    logger.info("Node 6 [Behavioral Risk] starting — claim=%s", claim_id)
    t0 = time.perf_counter()

    # ── Defaults ──────────────────────────────────────────────────────────────
    result: dict[str, Any] = {
        "behavioral_checks": {},
        "behavioral_risk_score": 0.0,
        "behavioral_flags": [],
        "node_results": {},
        "messages": [],
    }

    claim_metadata = state.get("claim_metadata")

    if not claim_metadata:
        logger.warning("Node 6: no claim metadata — skipping")
        result["behavioral_flags"] = ["SKIPPED: no claim metadata available"]
        result["behavioral_checks"] = {"skipped": True}
        result["node_results"] = {
            "behavioral_risk": {
                "score": 0.0,
                "flags": ["SKIPPED: no claim metadata"],
                "details": {"skipped": True},
            }
        }
        result["messages"] = [
            AIMessage(content="Node 6 [Behavioral Risk] — skipped (no metadata)")
        ]
        return result

    try:
        analysis = analyze_behavioral_risk(claim_metadata)
        score  = analysis["risk_score"]
        flags  = analysis["flags"]
        checks = analysis["checks"]
    except Exception as exc:
        logger.error("Node 6: analysis failed — %s", exc)
        result["behavioral_checks"] = {"error": str(exc)}
        result["node_results"] = {
            "behavioral_risk": {
                "score": 0.0,
                "flags": [f"ERROR: {exc}"],
                "details": {"error": str(exc)},
            }
        }
        result["messages"] = [
            AIMessage(content=f"Node 6 [Behavioral Risk] — error: {exc}")
        ]
        return result

    elapsed = time.perf_counter() - t0
    summary = (
        f"Node 6 [Behavioral Risk] — score={score}, "
        f"flags={len(flags)}, time={elapsed:.3f}s"
    )
    logger.info(summary)

    result["behavioral_checks"]     = checks
    result["behavioral_risk_score"] = score
    result["behavioral_flags"]      = flags
    result["node_results"] = {
        "behavioral_risk": {
            "score": score,
            "flags": flags,
            "details": checks,
        }
    }
    result["messages"] = [AIMessage(content=summary)]
    return result
