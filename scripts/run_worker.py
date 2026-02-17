"""
Background Worker
Runs scheduled tasks: retention sweeps, fraud re-analysis, etc.
Can be extended with Celery for production scale.
"""
import logging
import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.compliance.retention_policy import RetentionPolicy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_daily_retention_sweep():
    """Run the daily data retention sweep"""
    db = SessionLocal()
    try:
        logger.info("Starting daily retention sweep...")
        policy = RetentionPolicy(db)
        result = policy.run_retention_sweep()
        logger.info(f"Retention sweep complete: {result}")
    except Exception as e:
        logger.error(f"Retention sweep failed: {e}")
    finally:
        db.close()


def run_worker():
    """
    Simple worker loop.
    In production: replace with Celery + Redis beat scheduler.
    """
    logger.info("InsureFlow-AI Worker started")

    while True:
        try:
            # Daily retention sweep (run every 24 hours)
            run_daily_retention_sweep()

            logger.info("Worker sleeping for 24 hours...")
            time.sleep(86400)  # 24 hours

        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
            break
        except Exception as e:
            logger.error(f"Worker error: {e}. Retrying in 60 seconds...")
            time.sleep(60)


if __name__ == "__main__":
    run_worker()