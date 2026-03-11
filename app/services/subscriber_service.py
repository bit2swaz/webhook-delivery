"""subscriber crud service - async sqlalchemy queries."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Subscriber
from app.db.schemas import SubscriberCreate, SubscriberUpdate


async def create_subscriber(db: AsyncSession, data: SubscriberCreate) -> Subscriber:
    """persist a new subscriber and return it.

    Args:
        db: active async session.
        data: validated subscriber creation payload.

    Returns:
        the newly created Subscriber instance (not yet committed).
    """
    sub = Subscriber(
        name=data.name,
        url=str(data.url),
        secret=data.secret,
        event_types=data.event_types,
        enabled=data.enabled,
    )
    db.add(sub)
    await db.flush()
    await db.refresh(sub)
    return sub


async def get_subscriber(db: AsyncSession, subscriber_id: uuid.UUID) -> Subscriber | None:
    """fetch a single subscriber by primary key.

    Args:
        db: active async session.
        subscriber_id: uuid of the subscriber to look up.

    Returns:
        Subscriber if found, None otherwise.
    """
    result = await db.execute(select(Subscriber).where(Subscriber.id == subscriber_id))
    return result.scalar_one_or_none()


async def list_subscribers(
    db: AsyncSession,
    limit: int = 100,
    offset: int = 0,
) -> list[Subscriber]:
    """return all subscribers with optional pagination.

    Args:
        db: active async session.
        limit: maximum number of rows to return.
        offset: number of rows to skip.

    Returns:
        list of Subscriber instances ordered by creation time.
    """
    result = await db.execute(
        select(Subscriber).order_by(Subscriber.created_at.asc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def update_subscriber(
    db: AsyncSession,
    subscriber_id: uuid.UUID,
    data: SubscriberUpdate,
) -> Subscriber | None:
    """apply a partial update to an existing subscriber.

    Only fields explicitly set in ``data`` are modified. Returns None if the
    subscriber does not exist.

    Args:
        db: active async session.
        subscriber_id: uuid of the subscriber to update.
        data: partial update payload; unset fields are ignored.

    Returns:
        updated Subscriber, or None if not found.
    """
    sub = await get_subscriber(db, subscriber_id)
    if sub is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    if "url" in update_data and update_data["url"] is not None:
        update_data["url"] = str(update_data["url"])

    for key, value in update_data.items():
        setattr(sub, key, value)

    await db.flush()
    await db.refresh(sub)
    return sub


async def delete_subscriber(db: AsyncSession, subscriber_id: uuid.UUID) -> bool:
    """hard-delete a subscriber.

    Args:
        db: active async session.
        subscriber_id: uuid of the subscriber to remove.

    Returns:
        True if the subscriber was found and deleted, False otherwise.
    """
    sub = await get_subscriber(db, subscriber_id)
    if sub is None:
        return False

    await db.delete(sub)
    await db.flush()
    return True
