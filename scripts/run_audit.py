"""
Standalone auditor agent entry point — designed for OS cron / Cloud Scheduler.

Usage (manual test):
    cd insureflow-backend
    python -m scripts.run_audit

Cron (daily at 2 AM server time):
    0 2 * * *  cd /app && python -m scripts.run_audit >> /logs/audit.log 2>&1

Docker (Cloud Run Jobs / scheduled container):
    Use the same image with: --command python --args "-m,scripts.run_audit"

Exit codes:
    0  — sweep completed (with or without findings)
    1  — sweep failed with an unhandled exception
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

# Ensure the app package resolves correctly when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("run_audit")


async def _run() -> int:
    """Execute one full audit sweep.  Returns 0 on success, 1 on failure."""
    from datetime import datetime, timezone

    from app.db.session import AsyncSessionLocal
    from app.ai_agents.auditor.graph import run_audit_sweep

    now = datetime.now(timezone.utc)
    run_id = f"audit-{now.strftime('%Y-%m-%dT%H:%M:%S')}"

    logger.info("=" * 60)
    logger.info("Auditor sweep starting | run_id=%s", run_id)
    logger.info("=" * 60)

    try:
        async with AsyncSessionLocal() as db:
            result = await run_audit_sweep(run_id=run_id, db=db)

        findings_n = result.get("findings_count", 0)
        errors = result.get("errors", {})

        logger.info(
            "Sweep complete | findings=%d | tool_errors=%d",
            findings_n,
            len(errors),
        )
        if result.get("summary"):
            logger.info("EXECUTIVE SUMMARY:\n%s", result["summary"])
        if errors:
            logger.warning("Tool errors encountered:\n%s", errors)

        return 0

    except Exception as exc:
        logger.exception("Auditor sweep FAILED | run_id=%s | error=%s", run_id, exc)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(_run())
    sys.exit(exit_code)
