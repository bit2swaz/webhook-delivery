"""deliver_webhook celery task with retry and backoff logic."""

from __future__ import annotations

from app.tasks.celery_app import celery_app


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.delivery.deliver_webhook",
    bind=True,
    max_retries=5,
)
def deliver_webhook(
    self: object,  # noqa: ARG001
    log_id: str,
    subscriber_id: str,
    payload: dict,  # type: ignore[type-arg]
) -> None:
    """deliver a webhook payload to a subscriber's endpoint.

    full implementation in phase 5.

    args:
        log_id: string uuid of the delivery log row.
        subscriber_id: string uuid of the target subscriber.
        payload: the event payload dict to POST.
    """
