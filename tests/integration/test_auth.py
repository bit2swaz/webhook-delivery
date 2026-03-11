"""integration tests for the auth endpoints and verify_jwt dependency."""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_post_auth_token_returns_access_token(async_client: AsyncClient) -> None:
    """POST /auth/token issues a jwt with the correct response shape."""
    resp = await async_client.post("/auth/token")
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0


@pytest.mark.asyncio
async def test_get_auth_me_with_valid_bearer_returns_payload(async_client: AsyncClient) -> None:
    """GET /auth/me with a valid bearer token returns the decoded claims."""
    token_resp = await async_client.post("/auth/token")
    token = token_resp.json()["access_token"]

    me_resp = await async_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    payload = me_resp.json()
    assert "sub" in payload
    assert "exp" in payload


@pytest.mark.asyncio
async def test_get_auth_me_with_no_auth_returns_401(async_client: AsyncClient) -> None:
    """GET /auth/me without an Authorization header returns 401."""
    resp = await async_client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_auth_me_with_malformed_token_returns_401(async_client: AsyncClient) -> None:
    """GET /auth/me with a garbage bearer token returns 401."""
    resp = await async_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not.a.real.token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_auth_me_with_expired_token_returns_401(async_client: AsyncClient) -> None:
    """GET /auth/me with an expired bearer token returns 401."""
    expired_token = create_access_token(
        {"sub": "test-service"},
        expires_delta=timedelta(days=-1),
    )
    resp = await async_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401
