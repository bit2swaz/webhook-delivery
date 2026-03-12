"""integration tests for the _run_delivery task function with real postgresql.

tests the complete delivery lifecycle: success, failed (retry), and dead-letter
paths using real db rows and mocked http client.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from celery.exceptions import MaxRetriesExceededError, Retry
from sqlalchemy import select

from app.db.models import DeliveryLog, Event, Subscriber
from app.tasks.delivery import BACKOFF_SCHEDULE, _run_delivery

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# helpers (sync - no async marker needed)
# ---------------------------------------------------------------------------


def _mock_task(retries: int = 0) -> MagicMock:
    """return a minimal mock celery task with configurable retry count."""
    task = MagicMock()
    task.request.retries = retries
    return task


async def _seed_delivery(db_session) -> tuple[Subscriber, Event, DeliveryLog]:
    """seed one subscriber, event, and pending delivery log row."""
    sub = Subscriber(
        name="delivery-test-sub",
        url="https://webhook.example.com/hook",
        event_types=[],
        enabled=True,
    )
    db_session.add(sub)

    event = Event(event_type="order.created", payload={"order_id": 99})
    db_session.add(event)
    await db_session.flush()

    log = DeliveryLog(
        event_id=event.id,
        subscriber_id=sub.id,
        status="pending",
        attempt_number=0,
    )
    db_session.add(log)
    await db_session.commit()

    return sub, event, log


def _mock_http_response(status_code: int, *, is_success: bool) -> MagicMock:
    """return a mock httpx response with the given status."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = is_success
    return resp


# ---------------------------------------------------------------------------
# success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delivery_marks_success_on_200_response(
    db_session,
    clean_tables,
    sync_test_session_factory,
) -> None:
    """_run_delivery sets status=success and records response_status when upstream returns 200."""
    sub, _event, log = await _seed_delivery(db_session)

    mock_task = _mock_task(retries=0)
    mock_resp = _mock_http_response(200, is_success=True)

    with (
        patch("app.tasks.delivery.SyncSession", sync_test_session_factory),
        patch("app.tasks.delivery.httpx.Client") as mock_client,
        patch("app.tasks.delivery.record_success"),
        patch("app.tasks.delivery.record_duration"),
    ):
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp
        _run_delivery(mock_task, str(log.id), str(sub.id), {"order_id": 99})

    result = await db_session.execute(
        select(DeliveryLog)
        .execution_options(populate_existing=True)
        .where(DeliveryLog.id == log.id)
    )
    updated = result.scalar_one()
    assert updated.status == "success"
    assert updated.response_status == 200


@pytest.mark.asyncio
async def test_delivery_records_duration_ms_on_success(
    db_session,
    clean_tables,
    sync_test_session_factory,
) -> None:
    """_run_delivery writes a non-null duration_ms to the log on success."""
    sub, _event, log = await _seed_delivery(db_session)

    mock_task = _mock_task(retries=0)
    mock_resp = _mock_http_response(200, is_success=True)

    with (
        patch("app.tasks.delivery.SyncSession", sync_test_session_factory),
        patch("app.tasks.delivery.httpx.Client") as mock_client,
        patch("app.tasks.delivery.record_success"),
        patch("app.tasks.delivery.record_duration"),
    ):
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp
        _run_delivery(mock_task, str(log.id), str(sub.id), {})

    result = await db_session.execute(
        select(DeliveryLog)
        .execution_options(populate_existing=True)
        .where(DeliveryLog.id == log.id)
    )
    updated = result.scalar_one()
    assert updated.duration_ms is not None
    assert updated.duration_ms >= 0


@pytest.mark.asyncio
async def test_delivery_sets_attempt_number_from_retry_count(
    db_session,
    clean_tables,
    sync_test_session_factory,
) -> None:
    """attempt_number in the db equals task.request.retries + 1."""
    sub, _event, log = await _seed_delivery(db_session)

    mock_task = _mock_task(retries=2)  # 3rd attempt
    mock_resp = _mock_http_response(200, is_success=True)

    with (
        patch("app.tasks.delivery.SyncSession", sync_test_session_factory),
        patch("app.tasks.delivery.httpx.Client") as mock_client,
        patch("app.tasks.delivery.record_success"),
        patch("app.tasks.delivery.record_duration"),
    ):
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp
        _run_delivery(mock_task, str(log.id), str(sub.id), {})

    result = await db_session.execute(
        select(DeliveryLog)
        .execution_options(populate_existing=True)
        .where(DeliveryLog.id == log.id)
    )
    updated = result.scalar_one()
    assert updated.attempt_number == 3


# ---------------------------------------------------------------------------
# failed path (retryable error)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delivery_marks_failed_on_500_response(
    db_session,
    clean_tables,
    sync_test_session_factory,
) -> None:
    """_run_delivery sets status=failed when upstream returns a non-success status."""
    sub, _event, log = await _seed_delivery(db_session)

    mock_task = _mock_task(retries=0)
    mock_task.retry.side_effect = Retry()
    mock_resp = _mock_http_response(500, is_success=False)

    with (
        patch("app.tasks.delivery.SyncSession", sync_test_session_factory),
        patch("app.tasks.delivery.httpx.Client") as mock_client,
        patch("app.tasks.delivery.record_failed"),
    ):
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp
        with pytest.raises(Retry):
            _run_delivery(mock_task, str(log.id), str(sub.id), {})

    result = await db_session.execute(
        select(DeliveryLog)
        .execution_options(populate_existing=True)
        .where(DeliveryLog.id == log.id)
    )
    updated = result.scalar_one()
    assert updated.status == "failed"
    assert updated.response_status == 500


@pytest.mark.asyncio
async def test_delivery_sets_next_retry_at_on_failure(
    db_session,
    clean_tables,
    sync_test_session_factory,
) -> None:
    """_run_delivery sets next_retry_at based on the backoff schedule."""
    sub, _event, log = await _seed_delivery(db_session)

    mock_task = _mock_task(retries=0)
    mock_task.retry.side_effect = Retry()
    mock_resp = _mock_http_response(500, is_success=False)

    with (
        patch("app.tasks.delivery.SyncSession", sync_test_session_factory),
        patch("app.tasks.delivery.httpx.Client") as mock_client,
        patch("app.tasks.delivery.record_failed"),
    ):
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp
        with pytest.raises(Retry):
            _run_delivery(mock_task, str(log.id), str(sub.id), {})

    result = await db_session.execute(
        select(DeliveryLog)
        .execution_options(populate_existing=True)
        .where(DeliveryLog.id == log.id)
    )
    updated = result.scalar_one()
    assert updated.next_retry_at is not None


# ---------------------------------------------------------------------------
# dead-letter path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delivery_marks_dead_after_max_retries(
    db_session,
    clean_tables,
    sync_test_session_factory,
) -> None:
    """_run_delivery sets status=dead when max retries are exhausted."""
    sub, _event, log = await _seed_delivery(db_session)

    mock_task = _mock_task(retries=len(BACKOFF_SCHEDULE))
    mock_task.retry.side_effect = MaxRetriesExceededError()
    mock_resp = _mock_http_response(500, is_success=False)

    with (
        patch("app.tasks.delivery.SyncSession", sync_test_session_factory),
        patch("app.tasks.delivery.httpx.Client") as mock_client,
        patch("app.tasks.delivery.record_failed"),
        patch("app.tasks.delivery.record_dead"),
    ):
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp
        # no exception should propagate - MaxRetriesExceededError is caught internally
        _run_delivery(mock_task, str(log.id), str(sub.id), {})

    result = await db_session.execute(
        select(DeliveryLog)
        .execution_options(populate_existing=True)
        .where(DeliveryLog.id == log.id)
    )
    updated = result.scalar_one()
    assert updated.status == "dead"


@pytest.mark.asyncio
async def test_delivery_marks_dead_on_connection_error(
    db_session,
    clean_tables,
    sync_test_session_factory,
) -> None:
    """_run_delivery handles connection errors identically to http errors at max retries."""
    sub, _event, log = await _seed_delivery(db_session)

    mock_task = _mock_task(retries=len(BACKOFF_SCHEDULE))
    mock_task.retry.side_effect = MaxRetriesExceededError()

    with (
        patch("app.tasks.delivery.SyncSession", sync_test_session_factory),
        patch("app.tasks.delivery.httpx.Client") as mock_client,
        patch("app.tasks.delivery.record_failed"),
        patch("app.tasks.delivery.record_dead"),
    ):
        mock_client.return_value.__enter__.return_value.post.side_effect = ConnectionError(
            "timeout"
        )
        _run_delivery(mock_task, str(log.id), str(sub.id), {})

    result = await db_session.execute(
        select(DeliveryLog)
        .execution_options(populate_existing=True)
        .where(DeliveryLog.id == log.id)
    )
    updated = result.scalar_one()
    assert updated.status == "dead"
