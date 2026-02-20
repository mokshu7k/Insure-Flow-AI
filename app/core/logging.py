"""
Structured logging setup.
"""
from __future__ import annotations

import logging
import sys

from app.config import settings


def setup_logging() -> None:
    """Configure root logger with level and format."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    # File handler — create directory if missing
    if settings.LOG_FILE:
        import os
        os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)
        handlers.append(logging.FileHandler(settings.LOG_FILE, encoding="utf-8"))

    logging.basicConfig(
        level=log_level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
        force=True,
    )

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "asyncio", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
