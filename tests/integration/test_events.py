"""integration tests for event ingestion routes."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_post_event_returns_202_with_event_id(authed_client) -> None:
    """POST /events returns 202 and a json body with event_id and status queued."""
    with patch("app.api.routes.events.fan_out_event") as mock_task:
        mock_task.delay.return_value = None
        resp = await authed_client.post(
            "/events/",
            json={"event_type": "order.created", "payload": {"order_id": 1}},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert "event_id" in body
    assert body["status"] == "queued"
    uuid.UUID(body["event_id"])  # must be a valid uuid


@pytest.mark.asyncio
async def test_post_event_calls_fanout_delay_with_event_id(authed_client) -> None:
    """POST /events calls fan_out_event.delay with the string uuid of the new event."""
    with patch("app.api.routes.events.fan_out_event") as mock_task:
        mock_task.delay.return_value = None
        resp = await authed_client.post(
            "/events/",
            json={"event_type": "payment.completed", "payload": {"amount": 99}},
        )

    assert resp.status_code == 202
    event_id = resp.json()["event_id"]
    mock_task.delay.assert_called_once_with(event_id, "payment.completed", {"amount": 99})


@pytest.mark.asyncio
async def test_post_event_without_jwt_returns_401(async_client) -> None:
    """POST /events without an authorization header returns 401."""
    resp = await async_client.post(
        "/events/",
        json={"event_type": "test.event", "payload": {}},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_event_missing_event_type_returns_422(authed_client) -> None:
    """POST /events with no event_type field returns 422 validation error."""
    with patch("app.api.routes.events.fan_out_event"):
        resp = await authed_client.post(
            "/events/",
            json={"payload": {"foo": "bar"}},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_event_non_dict_payload_returns_422(authed_client) -> None:
    """POST /events with a non-dict payload value returns 422 validation error."""
    with patch("app.api.routes.events.fan_out_event"):
        resp = await authed_client.post(
            "/events/",
            json={"event_type": "test.event", "payload": "not-a-dict"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_event_returns_200_with_deliveries(authed_client) -> None:
    """GET /events/:id returns 200 with event fields and an empty deliveries list."""
    with patch("app.api.routes.events.fan_out_event") as mock_task:
        mock_task.delay.return_value = None
        post_resp = await authed_client.post(
            "/events/",
            json={"event_type": "user.signup", "payload": {"uid": "abc"}},
        )

    event_id = post_resp.json()["event_id"]
    resp = await authed_client.get(f"/events/{event_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == event_id
    assert body["event_type"] == "user.signup"
    assert body["payload"] == {"uid": "abc"}
    assert isinstance(body["deliveries"], list)


@pytest.mark.asyncio
async def test_get_event_unknown_id_returns_404(authed_client) -> None:
    """GET /events/:id with an unknown uuid returns 404."""
    unknown = str(uuid.uuid4())
    resp = await authed_client.get(f"/events/{unknown}")
    assert resp.status_code == 404
