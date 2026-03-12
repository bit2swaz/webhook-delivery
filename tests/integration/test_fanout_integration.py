"""integration tests for fan_out_event task with real postgresql.

verifies subscriber matching, wildcard handling, disabled-subscriber exclusion,
and that deliver_webhook is dispatched once per matching subscriber.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.db.models import DeliveryLog, Event, Subscriber
from app.tasks.fanout import fan_out_event

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _flush_subs(db_session, *subs) -> None:
    """add and flush multiple subscribers in one call."""
    for s in subs:
        db_session.add(s)
    await db_session.flush()


# ---------------------------------------------------------------------------
# fan-out matching tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fanout_creates_log_for_matching_and_wildcard_subscribers(
    db_session,
    clean_tables,
    sync_test_session_factory,
) -> None:
    """fan_out_event creates exactly 3 logs for 2 matching + 1 wildcard, not 4.

    subscriber breakdown:
      - matching-1: event_types=["order.created"]  -> gets a log
      - matching-2: event_types=["order.created"]  -> gets a log
      - wildcard:   event_types=[]                  -> gets a log
      - wrong-type: event_types=["payment.done"]   -> excluded
    """
    await _flush_subs(
        db_session,
        Subscriber(
            name="matching-1",
            url="https://a.example.com",
            event_types=["order.created"],
            enabled=True,
        ),
        Subscriber(
            name="matching-2",
            url="https://b.example.com",
            event_types=["order.created"],
            enabled=True,
        ),
        Subscriber(name="wildcard", url="https://c.example.com", event_types=[], enabled=True),
        Subscriber(
            name="wrong-type",
            url="https://d.example.com",
            event_types=["payment.done"],
            enabled=True,
        ),
    )

    event = Event(event_type="order.created", payload={"order_id": 42})
    db_session.add(event)
    await db_session.commit()

    with (
        patch("app.tasks.fanout.SyncSession", sync_test_session_factory),
        patch("app.tasks.delivery.deliver_webhook") as mock_deliver,
    ):
        mock_deliver.apply_async.return_value = None
        fan_out_event(str(event.id), "order.created", {"order_id": 42})

    result = await db_session.execute(select(DeliveryLog).where(DeliveryLog.event_id == event.id))
    logs = result.scalars().all()
    assert len(logs) == 3


@pytest.mark.asyncio
async def test_fanout_excludes_wrong_event_type(
    db_session,
    clean_tables,
    sync_test_session_factory,
) -> None:
    """subscriber with non-matching event_types receives no delivery log."""
    await _flush_subs(
        db_session,
        Subscriber(
            name="wrong-type",
            url="https://e.example.com",
            event_types=["payment.done"],
            enabled=True,
        ),
    )

    event = Event(event_type="order.created", payload={})
    db_session.add(event)
    await db_session.commit()

    with (
        patch("app.tasks.fanout.SyncSession", sync_test_session_factory),
        patch("app.tasks.delivery.deliver_webhook") as mock_deliver,
    ):
        mock_deliver.apply_async.return_value = None
        fan_out_event(str(event.id), "order.created", {})

    result = await db_session.execute(select(DeliveryLog).where(DeliveryLog.event_id == event.id))
    logs = result.scalars().all()
    assert len(logs) == 0


@pytest.mark.asyncio
async def test_fanout_skips_disabled_subscriber(
    db_session,
    clean_tables,
    sync_test_session_factory,
) -> None:
    """disabled subscriber is excluded even when event type matches."""
    await _flush_subs(
        db_session,
        Subscriber(
            name="enabled",
            url="https://f.example.com",
            event_types=["order.created"],
            enabled=True,
        ),
        Subscriber(
            name="disabled",
            url="https://g.example.com",
            event_types=["order.created"],
            enabled=False,
        ),
    )

    event = Event(event_type="order.created", payload={})
    db_session.add(event)
    await db_session.commit()

    with (
        patch("app.tasks.fanout.SyncSession", sync_test_session_factory),
        patch("app.tasks.delivery.deliver_webhook") as mock_deliver,
    ):
        mock_deliver.apply_async.return_value = None
        fan_out_event(str(event.id), "order.created", {})

    result = await db_session.execute(select(DeliveryLog).where(DeliveryLog.event_id == event.id))
    logs = result.scalars().all()
    assert len(logs) == 1  # only the enabled subscriber


@pytest.mark.asyncio
async def test_fanout_deliver_called_with_correct_subscriber_id(
    db_session,
    clean_tables,
    sync_test_session_factory,
) -> None:
    """deliver_webhook.apply_async is called with the correct subscriber id."""
    sub = Subscriber(
        name="target",
        url="https://h.example.com",
        event_types=["test.event"],
        enabled=True,
    )
    db_session.add(sub)

    event = Event(event_type="test.event", payload={"x": 1})
    db_session.add(event)
    await db_session.commit()

    with (
        patch("app.tasks.fanout.SyncSession", sync_test_session_factory),
        patch("app.tasks.delivery.deliver_webhook") as mock_deliver,
    ):
        mock_deliver.apply_async.return_value = None
        fan_out_event(str(event.id), "test.event", {"x": 1})

    mock_deliver.apply_async.assert_called_once()
    call_args = mock_deliver.apply_async.call_args[1]["args"]
    # args = [log_id, subscriber_id, payload]
    assert call_args[1] == str(sub.id)
    assert call_args[2] == {"x": 1}


@pytest.mark.asyncio
async def test_fanout_delivery_logs_have_pending_status(
    db_session,
    clean_tables,
    sync_test_session_factory,
) -> None:
    """delivery logs created by fan_out_event start with status=pending."""
    sub = Subscriber(name="sub", url="https://i.example.com", event_types=[], enabled=True)
    db_session.add(sub)

    event = Event(event_type="any.event", payload={})
    db_session.add(event)
    await db_session.commit()

    with (
        patch("app.tasks.fanout.SyncSession", sync_test_session_factory),
        patch("app.tasks.delivery.deliver_webhook") as mock_deliver,
    ):
        mock_deliver.apply_async.return_value = None
        fan_out_event(str(event.id), "any.event", {})

    result = await db_session.execute(select(DeliveryLog).where(DeliveryLog.event_id == event.id))
    log = result.scalar_one()
    assert log.status == "pending"
