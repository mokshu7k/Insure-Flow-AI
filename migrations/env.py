"""
Alembic async env.py — runs migrations against asyncpg.
Supports both online (async) and offline modes.
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.db.base import Base

# Import all models so Alembic can detect all tables (required for autogenerate)
import app.models  # noqa: F401 — side-effect import registers all models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def ensure_db_exists() -> None:
    """Create the target database if it doesn't already exist (idempotent)."""
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
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        await engine.dispose()


async def run_async_migrations() -> None:
    await ensure_db_exists()
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
