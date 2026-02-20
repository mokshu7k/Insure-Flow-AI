"""
InsureFlow AI — FastAPI Application Entry Point
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import InsureFlowException
from app.core.logging import setup_logging
from app.api.router import api_router

setup_logging()
logger = logging.getLogger(__name__)



# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Starting InsureFlow AI v2...")
    # Add startup tasks here as stages are built:
    # e.g. warm up ML model, verify DB connectivity
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
