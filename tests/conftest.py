"""
Shared pytest fixtures.
Uses httpx.AsyncClient against the live FastAPI app — no mocking needed for integration tests.

For unit tests that don't need a DB, no special fixture is required.
For DB tests (Stage B2+), an async session fixture with rollback will be added here.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Async test client against the real app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c
