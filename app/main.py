"""
InsureFlow AI — FastAPI Application Entry Point
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError as SAOperationalError

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.core.exceptions import InsureFlowException
from app.core.logging import setup_logging
from app.api.router import api_router

setup_logging()
logger = logging.getLogger(__name__)


async def ensure_db_exists() -> None:
    """Create the application database if it does not already exist.

    Connects to the *postgres* maintenance database (always present on any
    PostgreSQL server) and issues CREATE DATABASE only when the target DB is
    missing.  Uses AUTOCOMMIT so the DDL statement runs outside a transaction.
    """
    db_name = settings.DATABASE_URL.rstrip("/").rsplit("/", 1)[-1]
    maintenance_url = settings.DATABASE_URL.rstrip("/").rsplit("/", 1)[0] + "/postgres"
    engine = create_async_engine(maintenance_url, isolation_level="AUTOCOMMIT", echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            )
            if result.fetchone() is None:
                logger.warning("Database '%s' not found — creating it now.", db_name)
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                logger.info("Database '%s' created successfully.", db_name)
            else:
                logger.info("Database '%s' already exists.", db_name)
    except Exception as exc:  # pragma: no cover
        logger.error("Could not ensure database exists: %s", exc)
        raise
    finally:
        await engine.dispose()


# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Starting InsureFlow AI v2...")
    await ensure_db_exists()
    yield
    logger.info("InsureFlow AI shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="InsureFlow AI",
    description="Compliance-First Insurance Claim Intelligence Platform",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Uses settings.ALLOWED_ORIGINS — NOT a wildcard.
# allow_credentials requires explicit origins (spec disallows credentials + "*").
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception handlers ───────────────────────────────────────────────────────
@app.exception_handler(InsureFlowException)
async def insureflow_exception_handler(request: Request, exc: InsureFlowException) -> JSONResponse:
    logger.warning("InsureFlow exception: %s", exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.error_code},
    )


@app.exception_handler(SAOperationalError)
async def db_operational_error_handler(request: Request, exc: SAOperationalError) -> JSONResponse:
    """Transient DB connectivity errors (pool timeout, host unreachable, etc.)"""
    logger.error(
        "Database connectivity error on %s %s: %s",
        request.method,
        request.url.path,
        str(exc.orig) if exc.orig else str(exc),
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable, please retry", "error_code": "DB_UNAVAILABLE"},
    )


@app.exception_handler(OSError)
async def os_error_handler(request: Request, exc: OSError) -> JSONResponse:
    """Network-level errors reaching the database (WSAEHOSTUNREACH, ECONNREFUSED, etc.)"""
    logger.error(
        "Network error on %s %s: [Errno %s] %s",
        request.method,
        request.url.path,
        exc.errno,
        exc.strerror,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable, please retry", "error_code": "DB_UNAVAILABLE"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"},
    )


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health_check() -> dict:
    return {"status": "healthy", "service": "InsureFlow-AI", "version": "2.0.0"}


# ── Prometheus metrics ────────────────────────────────────────────────────────
@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    from fastapi.responses import Response
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
