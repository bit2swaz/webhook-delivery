"""fan_out_event celery task - dispatches one delivery task per matching subscriber."""

from __future__ import annotations

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.fanout.fan_out_event")  # type: ignore[untyped-decorator]
def fan_out_event(event_id: str) -> None:
    """fan out an event to all matching subscribers.

    full implementation in phase 5.

    args:
        event_id: string uuid of the event to fan out.
    """
