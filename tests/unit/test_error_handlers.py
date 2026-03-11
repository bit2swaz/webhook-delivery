"""unit tests for global error handlers - phase 6.3."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token


def _make_crash_app() -> FastAPI:
    """minimal fastapi app with a crash route and the production exception handler."""
    from app.main import unhandled_exception_handler

    mini: FastAPI = FastAPI()

    @mini.get("/crash")
    async def crash() -> None:
        raise RuntimeError("deliberate crash for testing")

    mini.add_exception_handler(Exception, unhandled_exception_handler)
    return mini


@pytest.mark.anyio
async def test_unhandled_exception_returns_500() -> None:
    """unhandled exceptions must produce a 500 json response."""
    mini = _make_crash_app()
    async with AsyncClient(
        transport=ASGITransport(app=mini, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/crash")
    assert response.status_code == 500


@pytest.mark.anyio
async def test_unhandled_exception_body_is_safe() -> None:
    """500 response must not leak stack trace or internal exception detail."""
    mini = _make_crash_app()
    async with AsyncClient(
        transport=ASGITransport(app=mini, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/crash")
    body = response.json()
    assert body == {"detail": "Internal server error"}
    assert "traceback" not in body
    assert "RuntimeError" not in str(body)


@pytest.mark.anyio
async def test_http_exception_returns_correct_status(async_client: AsyncClient) -> None:
    """FastAPI HTTPExceptions must still return the correct status and json body."""
    response = await async_client.get("/nonexistent-route-12345")
    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.anyio
async def test_validation_error_returns_422(async_client: AsyncClient) -> None:
    """pydantic validation errors on request body must return 422."""
    token = create_access_token({"sub": "test"})
    response = await async_client.post(
        "/events/",
        json={},  # missing required event_type and payload
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
