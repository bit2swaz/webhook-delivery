"""integration tests for subscriber crud endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.db.schemas import SubscriberCreate
from app.services.subscriber_service import create_subscriber
from tests.factories import SubscriberFactory

# ---------------------------------------------------------------------------
# POST /subscribers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_subscriber_returns_201_with_id(authed_client: AsyncClient) -> None:
    """POST /subscribers with valid payload returns 201 and a uuid id."""
    data = SubscriberFactory.build()
    resp = await authed_client.post(
        "/subscribers",
        json={"name": data.name, "url": str(data.url), "event_types": []},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["name"] == data.name
    uuid.UUID(body["id"])  # must be a valid uuid


@pytest.mark.asyncio
async def test_post_subscriber_without_jwt_returns_401(async_client: AsyncClient) -> None:
    """POST /subscribers without auth header returns 401."""
    resp = await async_client.post(
        "/subscribers",
        json={"name": "test", "url": "https://test.example.com/webhook"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_subscriber_missing_url_returns_422(authed_client: AsyncClient) -> None:
    """POST /subscribers with no url field returns 422 validation error."""
    resp = await authed_client.post("/subscribers", json={"name": "no-url"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /subscribers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_subscribers_returns_200_list(
    authed_client: AsyncClient, db_session: object
) -> None:
    """GET /subscribers returns 200 and a list containing seeded subscribers."""
    from sqlalchemy.ext.asyncio import AsyncSession

    session: AsyncSession = db_session  # type: ignore[assignment]
    await create_subscriber(
        session, SubscriberCreate(name="s1", url="https://s1.example.com/webhook")
    )
    await create_subscriber(
        session, SubscriberCreate(name="s2", url="https://s2.example.com/webhook")
    )
    await session.commit()

    resp = await authed_client.get("/subscribers")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 2


@pytest.mark.asyncio
async def test_get_subscribers_without_jwt_returns_401(async_client: AsyncClient) -> None:
    """GET /subscribers without auth header returns 401."""
    resp = await async_client.get("/subscribers")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /subscribers/:id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_subscriber_by_id_returns_200(
    authed_client: AsyncClient, db_session: object
) -> None:
    """GET /subscribers/:id returns 200 with the correct subscriber."""
    from sqlalchemy.ext.asyncio import AsyncSession

    session: AsyncSession = db_session  # type: ignore[assignment]
    sub = await create_subscriber(
        session, SubscriberCreate(name="byid", url="https://byid.example.com/webhook")
    )
    await session.commit()

    resp = await authed_client.get(f"/subscribers/{sub.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "byid"


@pytest.mark.asyncio
async def test_get_subscriber_unknown_id_returns_404(authed_client: AsyncClient) -> None:
    """GET /subscribers/:id with unknown uuid returns 404."""
    resp = await authed_client.get(f"/subscribers/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /subscribers/:id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_subscriber_updates_fields(
    authed_client: AsyncClient, db_session: object
) -> None:
    """PUT /subscribers/:id with partial payload updates only those fields."""
    from sqlalchemy.ext.asyncio import AsyncSession

    session: AsyncSession = db_session  # type: ignore[assignment]
    sub = await create_subscriber(
        session,
        SubscriberCreate(name="original", url="https://original.example.com/webhook"),
    )
    await session.commit()

    resp = await authed_client.put(f"/subscribers/{sub.id}", json={"name": "updated"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "updated"
    assert "original" in body["url"]  # url unchanged


@pytest.mark.asyncio
async def test_put_subscriber_unknown_id_returns_404(authed_client: AsyncClient) -> None:
    """PUT /subscribers/:id with unknown uuid returns 404."""
    resp = await authed_client.put(f"/subscribers/{uuid.uuid4()}", json={"name": "x"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /subscribers/:id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_subscriber_returns_204(
    authed_client: AsyncClient, db_session: object
) -> None:
    """DELETE /subscribers/:id removes the subscriber and returns 204."""
    from sqlalchemy.ext.asyncio import AsyncSession

    session: AsyncSession = db_session  # type: ignore[assignment]
    sub = await create_subscriber(
        session,
        SubscriberCreate(name="to-delete", url="https://delete.example.com/webhook"),
    )
    await session.commit()

    resp = await authed_client.delete(f"/subscribers/{sub.id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_subscriber_unknown_id_returns_404(authed_client: AsyncClient) -> None:
    """DELETE /subscribers/:id with unknown uuid returns 404."""
    resp = await authed_client.delete(f"/subscribers/{uuid.uuid4()}")
    assert resp.status_code == 404
