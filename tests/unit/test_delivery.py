"""unit tests for deliver_webhook celery task.

tests call _run_delivery() directly to avoid celery proxy complications.
uses respx to mock httpx and MagicMock for the sync db session.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from app.tasks.delivery import BACKOFF_SCHEDULE, _run_delivery

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_log(
    *,
    status: str = "pending",
    attempt_number: int = 1,
) -> MagicMock:
    log = MagicMock()
    log.id = uuid.uuid4()
    log.status = status
    log.attempt_number = attempt_number
    log.attempted_at = None
    log.next_retry_at = None
    log.response_status = None
    log.duration_ms = None
    return log


def _make_subscriber(
    *,
    url: str = "https://hook.example.com/recv",
    secret: str | None = None,
) -> MagicMock:
    sub = MagicMock()
    sub.id = uuid.uuid4()
    sub.url = url
    sub.secret = secret
    return sub


def _make_task_self(retries: int = 0) -> MagicMock:
    """mimic the bound celery task self."""
    from celery.exceptions import Retry

    task_self = MagicMock()
    task_self.request.retries = retries
    retry_exc = Retry()
    task_self.retry.side_effect = lambda **kw: (_ for _ in ()).throw(retry_exc)
    return task_self


def _make_task_self_max_exceeded(retries: int = 0) -> MagicMock:
    """task self whose retry() raises MaxRetriesExceededError."""
    from celery.exceptions import MaxRetriesExceededError

    task_self = MagicMock()
    task_self.request.retries = retries
    task_self.retry.side_effect = MaxRetriesExceededError()
    return task_self


def _setup_db(log: MagicMock, sub: MagicMock) -> MagicMock:
    """return a SyncSession context manager that yields a db mock."""
    mock_db = MagicMock()
    mock_db.get.side_effect = lambda model, obj_id: (  # type: ignore[return-value]
        log if str(obj_id) == str(log.id) else sub
    )
    mock_db.commit = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=mock_db)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# 5.3 delivery task - status transitions
# ---------------------------------------------------------------------------


@respx.mock
def test_success_sets_status_and_response_code() -> None:
    """subscriber returns 200 -> log.status = 'success', response_status = 200."""
    sub = _make_subscriber()
    log = _make_log()
    payload: dict = {"order_id": 1}  # type: ignore[type-arg]

    respx.post(sub.url).mock(return_value=httpx.Response(200))
    ctx = _setup_db(log, sub)

    with patch("app.tasks.delivery.SyncSession", return_value=ctx):
        _run_delivery(_make_task_self(), str(log.id), str(sub.id), payload)

    assert log.status == "success"
    assert log.response_status == 200
    assert log.duration_ms is not None
    assert log.duration_ms >= 0


@respx.mock
def test_success_sets_attempted_at() -> None:
    """attempted_at is set on a successful delivery."""
    sub = _make_subscriber()
    log = _make_log()

    respx.post(sub.url).mock(return_value=httpx.Response(200))
    ctx = _setup_db(log, sub)

    with patch("app.tasks.delivery.SyncSession", return_value=ctx):
        _run_delivery(_make_task_self(), str(log.id), str(sub.id), {})

    assert log.attempted_at is not None


@respx.mock
def test_500_sets_failed_and_retries() -> None:
    """subscriber returns 500 -> log.status = 'failed', task retries with countdown."""
    from celery.exceptions import Retry

    sub = _make_subscriber()
    log = _make_log()
    task_self = _make_task_self(retries=0)

    respx.post(sub.url).mock(return_value=httpx.Response(500))
    ctx = _setup_db(log, sub)

    with patch("app.tasks.delivery.SyncSession", return_value=ctx):
        with pytest.raises(Retry):
            _run_delivery(task_self, str(log.id), str(sub.id), {})

    assert log.status == "failed"
    task_self.retry.assert_called_once()
    _, call_kwargs = task_self.retry.call_args
    assert call_kwargs["countdown"] == BACKOFF_SCHEDULE[0]


@respx.mock
def test_failed_sets_next_retry_at() -> None:
    """next_retry_at is set on a failed delivery."""
    from celery.exceptions import Retry

    sub = _make_subscriber()
    log = _make_log()

    respx.post(sub.url).mock(return_value=httpx.Response(500))
    ctx = _setup_db(log, sub)

    with patch("app.tasks.delivery.SyncSession", return_value=ctx):
        with pytest.raises(Retry):
            _run_delivery(_make_task_self(retries=0), str(log.id), str(sub.id), {})

    assert log.next_retry_at is not None


@respx.mock
def test_timeout_triggers_retry() -> None:
    """httpx timeout -> treated as failure, triggers retry."""
    from celery.exceptions import Retry

    sub = _make_subscriber()
    log = _make_log()
    task_self = _make_task_self(retries=0)

    respx.post(sub.url).mock(side_effect=httpx.TimeoutException("timeout"))
    ctx = _setup_db(log, sub)

    with patch("app.tasks.delivery.SyncSession", return_value=ctx):
        with pytest.raises(Retry):
            _run_delivery(task_self, str(log.id), str(sub.id), {})

    task_self.retry.assert_called_once()


@respx.mock
def test_dead_after_max_retries() -> None:
    """on MaxRetriesExceededError -> log.status = 'dead'."""
    sub = _make_subscriber()
    log = _make_log()
    task_self = _make_task_self_max_exceeded(retries=len(BACKOFF_SCHEDULE))

    respx.post(sub.url).mock(return_value=httpx.Response(500))
    ctx = _setup_db(log, sub)

    with patch("app.tasks.delivery.SyncSession", return_value=ctx):
        _run_delivery(task_self, str(log.id), str(sub.id), {})

    assert log.status == "dead"


@respx.mock
def test_sets_delivering_before_http_call() -> None:
    """log.status is set to 'delivering' before the http call is made."""
    sub = _make_subscriber()
    log = _make_log()
    statuses_during_call: list[str] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        statuses_during_call.append(log.status)
        return httpx.Response(200)

    respx.post(sub.url).mock(side_effect=_capture)
    ctx = _setup_db(log, sub)

    with patch("app.tasks.delivery.SyncSession", return_value=ctx):
        _run_delivery(_make_task_self(), str(log.id), str(sub.id), {})

    assert statuses_during_call == ["delivering"]


# ---------------------------------------------------------------------------
# 5.4 HMAC signing
# ---------------------------------------------------------------------------


@respx.mock
def test_hmac_header_present_when_secret_set() -> None:
    """X-Webhook-Signature header is sent when subscriber has a secret."""
    payload: dict = {"data": "value"}  # type: ignore[type-arg]
    sub = _make_subscriber(secret="mysecret")
    log = _make_log()
    received_headers: dict = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        received_headers.update(dict(request.headers))
        return httpx.Response(200)

    respx.post(sub.url).mock(side_effect=_capture)
    ctx = _setup_db(log, sub)

    with patch("app.tasks.delivery.SyncSession", return_value=ctx):
        _run_delivery(_make_task_self(), str(log.id), str(sub.id), payload)

    assert "x-webhook-signature" in received_headers
    body = json.dumps(payload).encode()
    expected = "sha256=" + hmac.new(b"mysecret", body, hashlib.sha256).hexdigest()
    assert received_headers["x-webhook-signature"] == expected


@respx.mock
def test_no_hmac_header_when_no_secret() -> None:
    """X-Webhook-Signature header is absent when subscriber has no secret."""
    sub = _make_subscriber(secret=None)
    log = _make_log()
    received_headers: dict = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        received_headers.update(dict(request.headers))
        return httpx.Response(200)

    respx.post(sub.url).mock(side_effect=_capture)
    ctx = _setup_db(log, sub)

    with patch("app.tasks.delivery.SyncSession", return_value=ctx):
        _run_delivery(_make_task_self(), str(log.id), str(sub.id), {})

    assert "x-webhook-signature" not in received_headers


def test_sign_payload_returns_correct_hex() -> None:
    """sign_payload produces sha256=<hex> matching a manual hmac computation."""
    from app.core.security import sign_payload

    secret = "s3cr3t"
    body = b'{"key":"val"}'
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert sign_payload(secret, body) == expected


# ---------------------------------------------------------------------------
# 5.5 backoff schedule parametrized
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("attempt_index", list(range(len(BACKOFF_SCHEDULE))))
@respx.mock
def test_backoff_countdown_matches_schedule(attempt_index: int) -> None:
    """for each attempt index, retry is called with the correct backoff countdown."""
    from celery.exceptions import Retry

    sub = _make_subscriber()
    log = _make_log()
    task_self = _make_task_self(retries=attempt_index)

    respx.post(sub.url).mock(return_value=httpx.Response(500))
    ctx = _setup_db(log, sub)

    with patch("app.tasks.delivery.SyncSession", return_value=ctx):
        with pytest.raises(Retry):
            _run_delivery(task_self, str(log.id), str(sub.id), {})

    _, call_kwargs = task_self.retry.call_args
    assert call_kwargs["countdown"] == BACKOFF_SCHEDULE[attempt_index]
