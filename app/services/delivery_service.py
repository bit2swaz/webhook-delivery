"""delivery log and event query service."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeliveryLog, Event
from app.db.schemas import EventCreate


async def create_event(db: AsyncSession, data: EventCreate) -> Event:
    """persist a new event row and return it.

    Args:
        db: active async session.
        data: validated event creation payload.

    Returns:
        the newly created Event instance (not yet committed).
    """
    event = Event(event_type=data.event_type, payload=data.payload)
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


async def get_event_with_deliveries(
    db: AsyncSession,
    event_id: uuid.UUID,
) -> tuple[Event | None, list[DeliveryLog]]:
    """return the event and all associated delivery log rows.

    Args:
        db: active async session.
        event_id: uuid of the event to look up.

    Returns:
        a tuple of (Event, list[DeliveryLog]). returns (None, []) when the
        event_id is not found.
    """
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if event is None:
        return None, []
    log_result = await db.execute(
        select(DeliveryLog)
        .where(DeliveryLog.event_id == event_id)
        .order_by(DeliveryLog.attempted_at)
    )
    logs = list(log_result.scalars().all())
    return event, logs


async def get_delivery_log(
    db: AsyncSession,
    log_id: uuid.UUID,
) -> DeliveryLog | None:
    """return a single delivery log row by id.

    Args:
        db: active async session.
        log_id: uuid of the delivery log row to fetch.

    Returns:
        DeliveryLog if found, None otherwise.
    """
    result = await db.execute(select(DeliveryLog).where(DeliveryLog.id == log_id))
    return result.scalar_one_or_none()
