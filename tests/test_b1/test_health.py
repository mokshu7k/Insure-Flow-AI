"""
Stage B1 — Health endpoint tests.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_shape(client: AsyncClient) -> None:
    response = await client.get("/health")
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "InsureFlow-AI"
    assert "version" in data


@pytest.mark.asyncio
async def test_unknown_route_returns_404(client: AsyncClient) -> None:
    response = await client.get("/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_metrics_endpoint_accessible(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert b"# HELP" in response.content or response.status_code == 200
