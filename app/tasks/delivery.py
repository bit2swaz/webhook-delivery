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

        log.status = "delivering"
        log.attempt_number = task_self.request.retries + 1
        log.attempted_at = datetime.now(UTC)
        db.commit()

    try:
        headers = {"Content-Type": "application/json"}

        if sub.secret:
            body = json.dumps(payload).encode()
            headers["X-Webhook-Signature"] = sign_payload(sub.secret, body)

        start = time.monotonic()
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(sub.url, json=payload, headers=headers)
        duration_ms = int((time.monotonic() - start) * 1000)

        with SyncSession() as db:
            log = db.get(DeliveryLog, log_id)
            log.response_status = resp.status_code
            log.duration_ms = duration_ms

            if resp.is_success:
                log.status = "success"
            else:
                raise Exception(f"subscriber returned {resp.status_code}")

            db.commit()

    except Exception as exc:
        attempt = task_self.request.retries

        try:
            countdown = BACKOFF_SCHEDULE[min(attempt, len(BACKOFF_SCHEDULE) - 1)]
            with SyncSession() as db:
                log = db.get(DeliveryLog, log_id)
                log.status = "failed"
                log.next_retry_at = datetime.now(UTC) + timedelta(seconds=countdown)
                db.commit()

            raise task_self.retry(exc=exc, countdown=countdown)

        except MaxRetriesExceededError:
            with SyncSession() as db:
                log = db.get(DeliveryLog, log_id)
                log.status = "dead"
                db.commit()


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

    sets the delivery log status through: pending -> delivering -> success/failed/dead.
    retries with exponential backoff on failures.

    args:
        log_id: string uuid of the delivery log row.
        subscriber_id: string uuid of the target subscriber.
        payload: the event payload dict to POST.
    """
    _run_delivery(self, log_id, subscriber_id, payload)
