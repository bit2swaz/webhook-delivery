"""unit tests for delivery service - mocked async session."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import DeliveryLog, Event
from app.db.schemas import EventCreate
from app.services.delivery_service import (
    create_event,
    get_delivery_log,
    get_event_with_deliveries,
)


def _mock_session() -> AsyncMock:
    """return a fresh async mock that mimics AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _execute_returning(value: object) -> AsyncMock:
    """helper: session.execute returns scalar_one_or_none = value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return AsyncMock(return_value=result)


def _execute_returning_scalars(values: list) -> AsyncMock:  # type: ignore[type-arg]
    """helper: session.execute returns scalars().all() = values."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return AsyncMock(return_value=result)


# ---------------------------------------------------------------------------
# create_event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_event_calls_add_and_flush() -> None:
    """create_event adds the model to the session and flushes."""
    session = _mock_session()
    data = EventCreate(event_type="order.created", payload={"order_id": 1})

    result = await create_event(session, data)

    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert isinstance(added, Event)
    session.flush.assert_awaited_once()
    assert result is added


@pytest.mark.asyncio
async def test_create_event_stores_event_type() -> None:
    """create_event persists the correct event_type on the model."""
    session = _mock_session()
    data = EventCreate(event_type="user.signup", payload={})

    await create_event(session, data)

    added = session.add.call_args[0][0]
    assert added.event_type == "user.signup"


@pytest.mark.asyncio
async def test_create_event_stores_payload() -> None:
    """create_event persists the payload dict on the model."""
    session = _mock_session()
    payload = {"amount": 42, "currency": "usd"}
    data = EventCreate(event_type="payment.completed", payload=payload)

    await create_event(session, data)

    added = session.add.call_args[0][0]
    assert added.payload == payload


# ---------------------------------------------------------------------------
# get_event_with_deliveries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_event_with_deliveries_returns_event_and_logs() -> None:
    """returns the matching event plus its delivery log rows."""
    event = MagicMock(spec=Event)
    event.id = uuid.uuid4()
    log1 = MagicMock(spec=DeliveryLog)
    log2 = MagicMock(spec=DeliveryLog)

    first_result = MagicMock()
    first_result.scalar_one_or_none.return_value = event

    second_result = MagicMock()
    second_result.scalars.return_value.all.return_value = [log1, log2]

    session = _mock_session()
    session.execute = AsyncMock(side_effect=[first_result, second_result])

    returned_event, logs = await get_event_with_deliveries(session, event.id)

    assert returned_event is event
    assert logs == [log1, log2]


@pytest.mark.asyncio
async def test_get_event_with_deliveries_returns_none_when_event_missing() -> None:
    """returns (None, []) when no event matches the given id."""
    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None

    session = _mock_session()
    session.execute = AsyncMock(return_value=not_found)

    returned_event, logs = await get_event_with_deliveries(session, uuid.uuid4())

    assert returned_event is None
    assert logs == []


# ---------------------------------------------------------------------------
# get_delivery_log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_delivery_log_returns_log_when_found() -> None:
    """returns the delivery log row for a known id."""
    log = MagicMock(spec=DeliveryLog)
    log.id = uuid.uuid4()

    session = _mock_session()
    session.execute = _execute_returning(log)

    result = await get_delivery_log(session, log.id)

    assert result is log


@pytest.mark.asyncio
async def test_get_delivery_log_returns_none_for_unknown_id() -> None:
    """returns None when no delivery log matches the given id."""
    session = _mock_session()
    session.execute = _execute_returning(None)

    result = await get_delivery_log(session, uuid.uuid4())

    assert result is None
