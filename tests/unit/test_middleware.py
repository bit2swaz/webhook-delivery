"""unit tests for request id middleware - phase 6.1."""

from __future__ import annotations

import re

import pytest
from httpx import AsyncClient

UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


@pytest.mark.anyio
async def test_response_has_x_request_id_header(async_client: AsyncClient) -> None:
    """every response must include an X-Request-ID header."""
    response = await async_client.get("/health")
    assert "x-request-id" in response.headers


@pytest.mark.anyio
async def test_x_request_id_is_uuid4(async_client: AsyncClient) -> None:
    """when no X-Request-ID is sent, the generated value must be a valid UUID4."""
    response = await async_client.get("/health")
    request_id = response.headers["x-request-id"]
    assert UUID4_RE.match(request_id), f"not a uuid4: {request_id!r}"


@pytest.mark.anyio
async def test_client_sent_request_id_is_echoed_back(async_client: AsyncClient) -> None:
    """if the client sends X-Request-ID, the same value must appear in the response."""
    custom_id = "my-custom-request-id-abc123"
    response = await async_client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.headers["x-request-id"] == custom_id
