"""integration tests for delivery log status and retry routes."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.db.models import DeliveryLog, Event, Subscriber


async def _make_subscriber(db_session) -> Subscriber:
    """seed a minimal subscriber row for fk compliance."""
    sub = Subscriber(
        name="test-sub",
        url="https://example.com/hook",
        enabled=True,
    )
    db_session.add(sub)
    await db_session.flush()
    return sub


@pytest.mark.asyncio
async def test_get_delivery_returns_200(authed_client, db_session) -> None:
    """GET /deliveries/:id returns 200 with the delivery log fields."""
    sub = await _make_subscriber(db_session)

    event = Event(event_type="order.shipped", payload={"order": 1})
    db_session.add(event)
    await db_session.flush()

    log = DeliveryLog(
        event_id=event.id,
        subscriber_id=sub.id,
        status="pending",
        attempt_number=1,
    )
    db_session.add(log)
    await db_session.commit()

    resp = await authed_client.get(f"/deliveries/{log.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(log.id)
    assert body["status"] == "pending"
    assert body["attempt_number"] == 1


@pytest.mark.asyncio
async def test_get_delivery_unknown_id_returns_404(authed_client) -> None:
    """GET /deliveries/:id with an unknown uuid returns 404."""
    resp = await authed_client.get(f"/deliveries/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_retry_delivery_dead_returns_202(authed_client, db_session) -> None:
    """GET /deliveries/:id/retry returns 202 when the delivery log has status dead."""
    sub = await _make_subscriber(db_session)

    event = Event(event_type="order.failed", payload={})
    db_session.add(event)
    await db_session.flush()

    log = DeliveryLog(
        event_id=event.id,
        subscriber_id=sub.id,
        status="dead",
        attempt_number=5,
    )
    db_session.add(log)
    await db_session.commit()

    with patch("app.api.routes.deliveries.deliver_webhook") as mock_task:
        mock_task.delay.return_value = None
        resp = await authed_client.get(f"/deliveries/{log.id}/retry")

    assert resp.status_code == 202
    mock_task.delay.assert_called_once_with(str(log.id))


@pytest.mark.asyncio
async def test_retry_delivery_non_dead_returns_400(authed_client, db_session) -> None:
    """GET /deliveries/:id/retry returns 400 when the delivery log is not dead."""
    sub = await _make_subscriber(db_session)

    event = Event(event_type="order.created", payload={})
    db_session.add(event)
    await db_session.flush()

    log = DeliveryLog(
        event_id=event.id,
        subscriber_id=sub.id,
        status="pending",
        attempt_number=1,
    )
    db_session.add(log)
    await db_session.commit()

    resp = await authed_client.get(f"/deliveries/{log.id}/retry")

    assert resp.status_code == 400
