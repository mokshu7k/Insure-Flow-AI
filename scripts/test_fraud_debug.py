"""Quick debug script — reproduce the 500 on fraud analysis."""
import asyncio
import sys
import traceback
import logging

sys.path.insert(0, "g:\\Insure-Flow-AI")

# Write everything to a file
logging.basicConfig(
    level=logging.DEBUG,
    filename="g:\\Insure-Flow-AI\\fraud_debug.log",
    filemode="w",
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
)
# Also print to stdout
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

log = logging.getLogger("fraud_debug")


async def main():
    from app.db.session import AsyncSessionLocal
    from app.services.fraud_service import run_fraud_analysis

    log.info("=== Starting fraud analysis debug test ===")
    async with AsyncSessionLocal() as db:
        try:
            result = await run_fraud_analysis(
                claim_id="e45879a4-cd35-46e0-b940-11840c52f491",
                actor_id="00000000-0000-0000-0000-000000000001",
                role="INSURER_ADMIN",
                db=db,
            )
            log.info("SUCCESS: score=%s risk=%s", result.fraud_score, result.risk_level)
        except Exception:
            log.error("=== EXCEPTION ===\n%s", traceback.format_exc())
    log.info("=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
