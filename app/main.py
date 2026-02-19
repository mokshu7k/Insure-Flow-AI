"""
InsureFlow-AI - Production FastAPI Application
Compliance-First Insurance Claim Intelligence Platform
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import logging

from app.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import InsureFlowException
from app.api.router import api_router
from app.db.session import engine
from app.models.base import Base

# Ensure Prometheus metrics are registered at import time
import app.ai_agents.fraud.metrics  # noqa: F401

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="InsureFlow-AI",
    description="Compliance-First Insurance Claim Intelligence Platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS Configuration (allow all for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


@app.on_event("startup")
async def startup_event():
    """Initialize database and system on startup"""
    logger.info("Starting InsureFlow-AI application...")
    
    # Create tables (in production, use Alembic migrations)
    if settings.CREATE_TABLES_ON_STARTUP:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    
    logger.info("InsureFlow-AI application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down InsureFlow-AI application...")


@app.exception_handler(InsureFlowException)
async def insureflow_exception_handler(request: Request, exc: InsureFlowException):
    """Global exception handler for custom exceptions"""
    logger.error(f"InsureFlow Exception: {exc.detail}", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.error_code},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unexpected errors"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"},
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "InsureFlow-AI",
        "version": "1.0.0"
    }


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    """
    Prometheus scrape endpoint.
    Exposes fraud-engine and application metrics in the Prometheus text format.
    Should be protected from public access in production (e.g. via ingress).
    """
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# Include API router
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )