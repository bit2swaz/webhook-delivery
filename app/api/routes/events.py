"""event ingest and fan-out endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_jwt
from app.db.schemas import EventCreate, EventDetailResponse, EventIngestResponse
from app.services.delivery_service import create_event, get_event_with_deliveries
from app.tasks.fanout import fan_out_event

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/", status_code=202, response_model=EventIngestResponse)
async def ingest_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _: str = Depends(verify_jwt),  # noqa: B008
) -> EventIngestResponse:
    """ingest an event, persist it, and enqueue fan-out."""
    event = await create_event(db, data)
    await db.commit()
    fan_out_event.delay(str(event.id))
    return EventIngestResponse(event_id=event.id, status="queued")


@router.get("/{event_id}", status_code=200, response_model=EventDetailResponse)
async def get_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _: str = Depends(verify_jwt),  # noqa: B008
) -> EventDetailResponse:
    """return a single event with its delivery log summaries."""
    event, logs = await get_event_with_deliveries(db, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return EventDetailResponse(
        id=event.id,
        event_type=event.event_type,
        payload=event.payload,
        received_at=event.received_at,
        deliveries=logs,
    )
