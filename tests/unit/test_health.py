"""tests for the /health endpoint - includes db and redis readiness checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# basic liveness
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_health_returns_200(async_client: AsyncClient) -> None:
    """GET /health responds with http 200 and status ok."""
    with (
        patch("app.api.routes.health._ping_db", new_callable=AsyncMock, return_value=True),
        patch("app.api.routes.health._ping_redis", new_callable=AsyncMock, return_value=True),
    ):
        response = await async_client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.anyio
async def test_health_includes_db_and_redis_keys(async_client: AsyncClient) -> None:
    """response body includes db and redis status fields."""
    with (
        patch("app.api.routes.health._ping_db", new_callable=AsyncMock, return_value=True),
        patch("app.api.routes.health._ping_redis", new_callable=AsyncMock, return_value=True),
    ):
        response = await async_client.get("/health")

    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"


# ---------------------------------------------------------------------------
# degraded scenarios
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_health_returns_503_when_db_down(async_client: AsyncClient) -> None:
    """GET /health returns 503 when the database is unreachable."""
    with (
        patch("app.api.routes.health._ping_db", new_callable=AsyncMock, return_value=False),
        patch("app.api.routes.health._ping_redis", new_callable=AsyncMock, return_value=True),
    ):
        response = await async_client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] == "error"
    assert body["redis"] == "ok"


@pytest.mark.anyio
async def test_health_returns_503_when_redis_down(async_client: AsyncClient) -> None:
    """GET /health returns 503 when redis is unreachable."""
    with (
        patch("app.api.routes.health._ping_db", new_callable=AsyncMock, return_value=True),
        patch("app.api.routes.health._ping_redis", new_callable=AsyncMock, return_value=False),
    ):
        response = await async_client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] == "ok"
    assert body["redis"] == "error"


@pytest.mark.anyio
async def test_health_returns_503_when_both_down(async_client: AsyncClient) -> None:
    """GET /health returns 503 and marks both components degraded."""
    with (
        patch("app.api.routes.health._ping_db", new_callable=AsyncMock, return_value=False),
        patch("app.api.routes.health._ping_redis", new_callable=AsyncMock, return_value=False),
    ):
        response = await async_client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] == "error"
    assert body["redis"] == "error"


# ---------------------------------------------------------------------------
# /metrics endpoint
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_metrics_endpoint_accessible_without_auth(async_client: AsyncClient) -> None:
    """GET /metrics returns 200 and prometheus text format - no jwt required."""
    response = await async_client.get("/metrics")

    assert response.status_code == 200
    # prometheus text format always starts with # HELP or metric lines
    assert b"#" in response.content or len(response.content) > 0
