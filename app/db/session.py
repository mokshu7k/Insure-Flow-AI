"""
Async SQLAlchemy engine and session factory.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────
# GCP Cloud SQL (asyncpg) — SSL is handled by the driver using the system
# CA bundle. No custom SSL context needed; sslmode=require in the URL is enough.
#
# pool_recycle=1800  — discard connections older than 30 min to avoid
#                      CloudSQL's idle-timeout silently closing them.
# pool_timeout=30    — raise immediately if no connection is available after 30 s.
# connect_args.timeout — asyncpg-level TCP connect timeout (30 s). Without
#                        this, a routing black-hole can hang for ~2 min.
#                        30 s is needed to accommodate Cloud SQL SSL handshakes
#                        when the pool must open a brand-new connection (e.g.
#                        background tasks that run after the request finishes).
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_timeout=30,
    connect_args={"timeout": 30},
    echo=settings.DEBUG,
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # objects usable after commit without reload
)


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, rolled back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
