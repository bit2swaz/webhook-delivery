"""fan_out_event celery task - dispatches one delivery task per matching subscriber."""

from __future__ import annotations

from app.db.models import DeliveryLog, Subscriber
from app.db.session import SyncSession
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.fanout.fan_out_event")  # type: ignore[untyped-decorator]
def fan_out_event(event_id: str, event_type: str, payload: dict) -> None:  # type: ignore[type-arg]
    """fan out an event to all matching subscribers.

    **Trigger:** dispatched by ``POST /events/`` via ``fan_out_event.delay()``
    immediately after the event row is committed.

    **Side effects:**
    - Creates one ``DeliveryLog`` row per matching subscriber (status=``pending``).
    - Enqueues one ``deliver_webhook`` task per created log via ``apply_async``.
    - Subscriber matching rules:
        - ``enabled=True`` is required.
        - ``event_types=[]`` (empty list) acts as a wildcard — matches all events.
        - Otherwise the subscriber's ``event_types`` array must contain
          ``event_type`` as an exact string match.

    Args:
        event_id: string uuid of the persisted ``Event`` row.
        event_type: event type string, e.g. ``'order.created'``.
        payload: the event payload dict to deliver to each subscriber.
    """
    # import here to avoid circular imports at module load time
    from app.tasks.delivery import deliver_webhook  # noqa: PLC0415

    with SyncSession() as db:
        subscribers = (
            db.query(Subscriber)
            .filter(
                Subscriber.enabled.is_(True),
            )
            .all()
        )

        # filter in python: empty event_types = wildcard; else must contain event_type
        matching = [s for s in subscribers if not s.event_types or event_type in s.event_types]

        for sub in matching:
            log = DeliveryLog(
                event_id=event_id,
                subscriber_id=str(sub.id),
                status="pending",
            )
            db.add(log)
            db.flush()

            deliver_webhook.apply_async(
                args=[str(log.id), str(sub.id), payload],
                countdown=0,
            )

        db.commit()
