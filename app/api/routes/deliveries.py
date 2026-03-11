"""delivery log status and manual retry endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_jwt
from app.db.schemas import DeliveryLogRead, RetryResponse
from app.services.delivery_service import get_delivery_log
from app.tasks.delivery import deliver_webhook

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


@router.get("/{log_id}", status_code=200, response_model=DeliveryLogRead)
async def get_delivery(
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _: str = Depends(verify_jwt),  # noqa: B008
) -> DeliveryLogRead:
    """return a single delivery log row."""
    log = await get_delivery_log(db, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="delivery log not found")
    return DeliveryLogRead.model_validate(log)


@router.get("/{log_id}/retry", status_code=202, response_model=RetryResponse)
async def retry_delivery(
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _: str = Depends(verify_jwt),  # noqa: B008
) -> RetryResponse:
    """re-enqueue a dead delivery for another attempt."""
    log = await get_delivery_log(db, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="delivery log not found")
    if log.status != "dead":
        raise HTTPException(
            status_code=400,
            detail="only dead deliveries can be retried",
        )
    deliver_webhook.delay(str(log.id))
    return RetryResponse(status="requeued")
