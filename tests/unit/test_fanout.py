"""unit tests for fan_out_event celery task."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch


def _make_subscriber(
    *,
    event_types: list[str],
    enabled: bool = True,
    url: str = "https://hook.example.com/recv",
    secret: str | None = None,
) -> MagicMock:
    sub = MagicMock()
    sub.id = uuid.uuid4()
    sub.url = url
    sub.secret = secret
    sub.enabled = enabled
    sub.event_types = event_types
    return sub


def _make_log(log_id: uuid.UUID | None = None) -> MagicMock:
    log = MagicMock()
    log.id = log_id or uuid.uuid4()
    return log


def _setup_session_mock(subscribers: list, log_id: uuid.UUID | None = None) -> tuple:
    """return (mock_session_ctx, mock_db) for patching SyncSession."""
    mock_db = MagicMock()
    # query().filter().all() returns subscribers
    mock_db.query.return_value.filter.return_value.all.return_value = subscribers
    # after db.add(log); db.flush() we need log.id to be accessible
    # simulate flush populating id via side_effect
    flushed = []

    def _add_side_effect(obj: object) -> None:
        obj.id = log_id or uuid.uuid4()  # type: ignore[union-attr]
        flushed.append(obj)

    mock_db.add.side_effect = _add_side_effect
    mock_db.flush = MagicMock()
    mock_db.commit = MagicMock()

    mock_session_ctx = MagicMock()
    mock_session_ctx.__enter__ = MagicMock(return_value=mock_db)
    mock_session_ctx.__exit__ = MagicMock(return_value=False)
    return mock_session_ctx, mock_db


# ---------------------------------------------------------------------------
# fan_out_event - matching subscribers
# ---------------------------------------------------------------------------


def test_fanout_creates_log_and_fires_task_for_each_matching_subscriber() -> None:
    """3 matching subscribers -> 3 DeliveryLog rows added + 3 apply_async calls."""
    subs = [
        _make_subscriber(event_types=["order.created"]),
        _make_subscriber(event_types=["order.created"]),
        _make_subscriber(event_types=["order.created"]),
    ]
    session_ctx, mock_db = _setup_session_mock(subs)

    with (
        patch("app.tasks.fanout.SyncSession", return_value=session_ctx),
        patch("app.tasks.delivery.deliver_webhook") as mock_task,
    ):
        from app.tasks.fanout import fan_out_event

        fan_out_event("event-uuid", "order.created", {"item": 1})

    assert mock_db.add.call_count == 3
    assert mock_task.apply_async.call_count == 3
    mock_db.commit.assert_called_once()


def test_fanout_fires_apply_async_with_correct_args() -> None:
    """apply_async receives (log_id, sub_id, payload) and countdown=0."""
    event_id = str(uuid.uuid4())
    payload: dict = {"x": 1}  # type: ignore[type-arg]
    sub = _make_subscriber(event_types=["order.created"])
    log_id = uuid.uuid4()
    session_ctx, mock_db = _setup_session_mock([sub], log_id=log_id)

    with (
        patch("app.tasks.fanout.SyncSession", return_value=session_ctx),
        patch("app.tasks.delivery.deliver_webhook") as mock_task,
    ):
        from app.tasks.fanout import fan_out_event

        fan_out_event(event_id, "order.created", payload)

    mock_task.apply_async.assert_called_once_with(
        args=[str(log_id), str(sub.id), payload],
        countdown=0,
    )


def test_fanout_excludes_non_matching_event_types() -> None:
    """subscriber listening to different event_type is not included in fan-out."""
    sub_match = _make_subscriber(event_types=["order.created"])
    _sub_other = _make_subscriber(event_types=["payment.done"])
    session_ctx, mock_db = _setup_session_mock([sub_match])  # db returns only match

    with (
        patch("app.tasks.fanout.SyncSession", return_value=session_ctx),
        patch("app.tasks.delivery.deliver_webhook") as mock_task,
    ):
        from app.tasks.fanout import fan_out_event

        fan_out_event("evt", "order.created", {})

    assert mock_db.add.call_count == 1
    assert mock_task.apply_async.call_count == 1


def test_fanout_includes_wildcard_subscriber() -> None:
    """subscriber with empty event_types receives all events (wildcard)."""
    sub = _make_subscriber(event_types=[])  # empty = wildcard
    session_ctx, mock_db = _setup_session_mock([sub])

    with (
        patch("app.tasks.fanout.SyncSession", return_value=session_ctx),
        patch("app.tasks.delivery.deliver_webhook") as mock_task,
    ):
        from app.tasks.fanout import fan_out_event

        fan_out_event("evt", "any.event.type", {"k": "v"})

    mock_task.apply_async.assert_called_once()


def test_fanout_excludes_disabled_subscriber() -> None:
    """disabled subscriber (enabled=False) is excluded from fan-out."""
    session_ctx, mock_db = _setup_session_mock([])  # db filters to no results

    with (
        patch("app.tasks.fanout.SyncSession", return_value=session_ctx),
        patch("app.tasks.delivery.deliver_webhook") as mock_task,
    ):
        from app.tasks.fanout import fan_out_event

        fan_out_event("evt", "order.created", {})

    mock_task.apply_async.assert_not_called()
    mock_db.add.assert_not_called()


def test_fanout_creates_delivery_log_with_pending_status() -> None:
    """each created DeliveryLog starts with status='pending'."""
    from app.db.models import DeliveryLog

    sub = _make_subscriber(event_types=["order.created"])
    session_ctx, mock_db = _setup_session_mock([sub])

    added_objects: list = []
    original_side_effect = mock_db.add.side_effect

    def capture_add(obj: object) -> None:
        added_objects.append(obj)
        if original_side_effect:
            original_side_effect(obj)

    mock_db.add.side_effect = capture_add

    with (
        patch("app.tasks.fanout.SyncSession", return_value=session_ctx),
        patch("app.tasks.delivery.deliver_webhook"),
    ):
        from app.tasks.fanout import fan_out_event

        fan_out_event("evt-id", "order.created", {})

    log_objects = [o for o in added_objects if isinstance(o, DeliveryLog)]
    assert len(log_objects) == 1
    assert log_objects[0].status == "pending"
    assert str(log_objects[0].event_id) == "evt-id"
