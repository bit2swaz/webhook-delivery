"""unit tests for subscriber crud service - mocked async session."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import Subscriber
from app.db.schemas import SubscriberCreate, SubscriberUpdate
from app.services.subscriber_service import (
    create_subscriber,
    delete_subscriber,
    get_subscriber,
    list_subscribers,
    update_subscriber,
)


def _mock_session() -> AsyncMock:
    """return a fresh async mock that mimics AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


def _execute_returning(value: object) -> AsyncMock:
    """helper: session.execute returns a result whose scalar_one_or_none = value."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = value
    mock_execute = AsyncMock(return_value=mock_result)
    return mock_execute


def _execute_returning_scalars(values: list[Subscriber]) -> AsyncMock:
    """helper: session.execute returns a result whose scalars().all() = values."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = values
    return AsyncMock(return_value=mock_result)


# ---------------------------------------------------------------------------
# create_subscriber
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_subscriber_calls_add_and_flush() -> None:
    """create_subscriber adds the model to the session and flushes."""
    session = _mock_session()
    data = SubscriberCreate(name="acme", url="https://acme.example.com/webhook")

    result = await create_subscriber(session, data)

    session.add.assert_called_once()
    added_obj = session.add.call_args[0][0]
    assert isinstance(added_obj, Subscriber)
    assert added_obj.name == "acme"
    session.flush.assert_awaited_once()
    assert result is added_obj


@pytest.mark.asyncio
async def test_create_subscriber_stores_url_as_string() -> None:
    """url is coerced from AnyHttpUrl to a plain string before persistence."""
    session = _mock_session()
    data = SubscriberCreate(name="x", url="https://x.example.com/webhook")

    await create_subscriber(session, data)

    added = session.add.call_args[0][0]
    assert isinstance(added.url, str)


@pytest.mark.asyncio
async def test_create_subscriber_propagates_event_types() -> None:
    """event_types list is passed through to the model."""
    session = _mock_session()
    data = SubscriberCreate(
        name="filtered",
        url="https://filtered.example.com/webhook",
        event_types=["order.created", "order.cancelled"],
    )

    await create_subscriber(session, data)

    added = session.add.call_args[0][0]
    assert added.event_types == ["order.created", "order.cancelled"]


# ---------------------------------------------------------------------------
# get_subscriber
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_subscriber_returns_subscriber_when_found() -> None:
    """get_subscriber returns the Subscriber from the result set."""
    sub = Subscriber(id=uuid.uuid4(), name="found", url="https://found.example.com/webhook")
    session = _mock_session()
    session.execute = _execute_returning(sub)

    result = await get_subscriber(session, sub.id)

    assert result is sub


@pytest.mark.asyncio
async def test_get_subscriber_returns_none_for_unknown_id() -> None:
    """get_subscriber returns None when no row matches the id."""
    session = _mock_session()
    session.execute = _execute_returning(None)

    result = await get_subscriber(session, uuid.uuid4())

    assert result is None


# ---------------------------------------------------------------------------
# list_subscribers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_subscribers_returns_all_rows() -> None:
    """list_subscribers returns every subscriber in the result."""
    sub1 = Subscriber(name="a", url="https://a.example.com/webhook")
    sub2 = Subscriber(name="b", url="https://b.example.com/webhook")
    session = _mock_session()
    session.execute = _execute_returning_scalars([sub1, sub2])

    result = await list_subscribers(session)

    assert len(result) == 2
    assert result[0] is sub1
    assert result[1] is sub2


@pytest.mark.asyncio
async def test_list_subscribers_returns_empty_list_when_none() -> None:
    """list_subscribers returns an empty list when no subscribers exist."""
    session = _mock_session()
    session.execute = _execute_returning_scalars([])

    result = await list_subscribers(session)

    assert result == []


# ---------------------------------------------------------------------------
# update_subscriber
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_subscriber_mutates_only_provided_fields() -> None:
    """update_subscriber only changes the fields present in SubscriberUpdate."""
    sub = Subscriber(
        id=uuid.uuid4(),
        name="original",
        url="https://original.example.com/webhook",
        enabled=True,
    )
    session = _mock_session()
    session.execute = _execute_returning(sub)

    result = await update_subscriber(session, sub.id, SubscriberUpdate(enabled=False))

    assert result is not None
    assert result.enabled is False
    assert result.name == "original"  # unchanged
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_subscriber_returns_none_for_unknown_id() -> None:
    """update_subscriber returns None when the id does not exist."""
    session = _mock_session()
    session.execute = _execute_returning(None)

    result = await update_subscriber(session, uuid.uuid4(), SubscriberUpdate(name="x"))

    assert result is None
    session.flush.assert_not_awaited()


# ---------------------------------------------------------------------------
# delete_subscriber
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_subscriber_returns_true_when_found() -> None:
    """delete_subscriber deletes the row and returns True."""
    sub = Subscriber(id=uuid.uuid4(), name="bye", url="https://bye.example.com/webhook")
    session = _mock_session()
    session.execute = _execute_returning(sub)

    result = await delete_subscriber(session, sub.id)

    assert result is True
    session.delete.assert_awaited_once_with(sub)
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_subscriber_returns_false_for_unknown_id() -> None:
    """delete_subscriber returns False without touching the session when not found."""
    session = _mock_session()
    session.execute = _execute_returning(None)

    result = await delete_subscriber(session, uuid.uuid4())

    assert result is False
    session.delete.assert_not_awaited()
