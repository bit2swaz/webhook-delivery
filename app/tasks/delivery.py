"""deliver_webhook celery task with retry and backoff logic."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from celery.exceptions import MaxRetriesExceededError

from app.core.security import sign_payload
from app.db.models import DeliveryLog, Subscriber
from app.db.session import SyncSession
from app.observability.metrics import record_dead, record_duration, record_failed, record_success
from app.tasks.celery_app import celery_app

# backoff schedule in seconds: 30s, 5m, 30m, 2h, 8h
BACKOFF_SCHEDULE = [30, 300, 1800, 7200, 28800]


def _run_delivery(
    task_self: Any,
    log_id: str,
    subscriber_id: str,
    payload: dict,  # type: ignore[type-arg]
) -> None:
    """core delivery logic extracted for testability.

    args:
        task_self: the bound celery task instance (provides .request and .retry).
        log_id: string uuid of the delivery log row.
        subscriber_id: string uuid of the target subscriber.
        payload: the event payload dict to POST.
    """
    with SyncSession() as db:
        log: DeliveryLog = db.get(DeliveryLog, log_id)
        sub: Subscriber = db.get(Subscriber, subscriber_id)

        # extract values before commit expires them and context-exit detaches sub
        sub_url: str = sub.url
        sub_secret: str | None = sub.secret

        log.status = "delivering"
        log.attempt_number = task_self.request.retries + 1
        log.attempted_at = datetime.now(UTC)
        db.commit()

    try:
        headers = {"Content-Type": "application/json"}

        if sub_secret:
            body = json.dumps(payload).encode()
            headers["X-Webhook-Signature"] = sign_payload(sub_secret, body)

        start = time.monotonic()
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(sub_url, json=payload, headers=headers)
        duration_ms = int((time.monotonic() - start) * 1000)

        with SyncSession() as db:
            log = db.get(DeliveryLog, log_id)
            log.response_status = resp.status_code
            log.duration_ms = duration_ms

            if resp.is_success:
                log.status = "success"

            db.commit()

        if resp.is_success:
            record_success(subscriber_id)
            record_duration(subscriber_id, duration_ms)
        else:
            raise Exception(f"subscriber returned {resp.status_code}")

    except Exception as exc:
        attempt = task_self.request.retries

        try:
            countdown = BACKOFF_SCHEDULE[min(attempt, len(BACKOFF_SCHEDULE) - 1)]
            with SyncSession() as db:
                log = db.get(DeliveryLog, log_id)
                log.status = "failed"
                log.next_retry_at = datetime.now(UTC) + timedelta(seconds=countdown)
                db.commit()

            record_failed(subscriber_id)
            raise task_self.retry(exc=exc, countdown=countdown)

        except MaxRetriesExceededError:
            with SyncSession() as db:
                log = db.get(DeliveryLog, log_id)
                log.status = "dead"
                db.commit()
            record_dead(subscriber_id)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.delivery.deliver_webhook",
    bind=True,
    max_retries=len(BACKOFF_SCHEDULE),
)
def deliver_webhook(
    self: Any,
    log_id: str,
    subscriber_id: str,
    payload: dict,  # type: ignore[type-arg]
) -> None:
    """deliver a webhook payload to a subscriber's endpoint.

    **Trigger:** dispatched by ``fan_out_event`` via ``apply_async`` once per
    matching (event, subscriber) pair, or directly via
    ``GET /deliveries/{id}/retry`` for manual re-queuing of dead deliveries.

    **Side effects:**
    - Transitions ``DeliveryLog.status``: pending → delivering → success/failed/dead.
    - Writes ``attempt_number``, ``attempted_at``, ``response_status``,
      ``duration_ms``, and (on failure) ``next_retry_at`` to the delivery log row.
    - Increments Prometheus counters via ``record_success``, ``record_failed``,
      or ``record_dead``.
    - Adds an ``X-Webhook-Signature: sha256=<hex>`` header when the subscriber
      has a signing secret configured.

    **Retry behaviour:** retries up to ``len(BACKOFF_SCHEDULE)`` times with
    countdown values taken from ``BACKOFF_SCHEDULE`` (30s, 5m, 30m, 2h, 8h).
    After exhausting all retries the delivery log is marked ``dead``.

    Args:
        self: the bound Celery task instance (provides ``request.retries`` and
            ``retry()``).
        log_id: string uuid of the ``DeliveryLog`` row to update.
        subscriber_id: string uuid of the target ``Subscriber``.
        payload: the event payload dict to POST as JSON.
    """
    _run_delivery(self, log_id, subscriber_id, payload)
