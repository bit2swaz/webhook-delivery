"""smoke test - GET /health returns 200.

this is the very first test written (red phase of 0.5 tdd).
it fails until main.py has the /health route.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_returns_200(async_client: AsyncClient) -> None:
    """GET /health responds with http 200 and status ok."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
