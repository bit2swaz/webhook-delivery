"""subscriber crud endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_jwt
from app.db.schemas import SubscriberCreate, SubscriberRead, SubscriberUpdate
from app.services.subscriber_service import (
    create_subscriber,
    delete_subscriber,
    get_subscriber,
    list_subscribers,
    update_subscriber,
)

router = APIRouter()


@router.post("", response_model=SubscriberRead, status_code=status.HTTP_201_CREATED)
async def create(
    data: SubscriberCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict[str, Any], Depends(verify_jwt)],
) -> SubscriberRead:
    """create a new subscriber.

    Returns:
        the created subscriber with its generated uuid.
    """
    sub = await create_subscriber(db, data)
    await db.commit()
    return SubscriberRead.model_validate(sub)


@router.get("", response_model=list[SubscriberRead])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict[str, Any], Depends(verify_jwt)],
    limit: int = 100,
    offset: int = 0,
) -> list[SubscriberRead]:
    """return a paginated list of all subscribers.

    Returns:
        list of subscriber read schemas.
    """
    subs = await list_subscribers(db, limit=limit, offset=offset)
    return [SubscriberRead.model_validate(s) for s in subs]


@router.get("/{subscriber_id}", response_model=SubscriberRead)
async def get_one(
    subscriber_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict[str, Any], Depends(verify_jwt)],
) -> SubscriberRead:
    """fetch a single subscriber by id.

    Returns:
        the matching subscriber.

    Raises:
        HTTPException: 404 if subscriber not found.
    """
    sub = await get_subscriber(db, subscriber_id)
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="subscriber not found",
        )
    return SubscriberRead.model_validate(sub)


@router.put("/{subscriber_id}", response_model=SubscriberRead)
async def update(
    subscriber_id: uuid.UUID,
    data: SubscriberUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict[str, Any], Depends(verify_jwt)],
) -> SubscriberRead:
    """partially update an existing subscriber.

    Returns:
        the updated subscriber.

    Raises:
        HTTPException: 404 if subscriber not found.
    """
    sub = await update_subscriber(db, subscriber_id, data)
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="subscriber not found",
        )
    await db.commit()
    return SubscriberRead.model_validate(sub)


@router.delete("/{subscriber_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    subscriber_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict[str, Any], Depends(verify_jwt)],
) -> None:
    """hard-delete a subscriber.

    Raises:
        HTTPException: 404 if subscriber not found.
    """
    found = await delete_subscriber(db, subscriber_id)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="subscriber not found",
        )
    await db.commit()
