"""delivery log status and manual retry endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_jwt
from app.api.openapi_examples import (
    BAD_REQUEST_EXAMPLE,
    DELIVERY_LOG_READ_EXAMPLE,
    NOT_FOUND_EXAMPLE,
    RETRY_RESPONSE_EXAMPLE,
)
from app.db.schemas import DeliveryLogRead, RetryResponse
from app.services.delivery_service import get_delivery_log
from app.tasks.delivery import deliver_webhook

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


@router.get(
    "/{log_id}",
    status_code=200,
    response_model=DeliveryLogRead,
    summary="Get delivery log",
    description=(
        "Returns a single delivery log row including status, response code, "
        "duration, attempt number, and retry schedule."
    ),
    response_description="Full delivery log record.",
    responses={
        200: {"content": {"application/json": {"example": DELIVERY_LOG_READ_EXAMPLE}}},
        404: {
            "description": "Delivery log not found.",
            "content": {"application/json": {"example": NOT_FOUND_EXAMPLE}},
        },
    },
)
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


@router.get(
    "/{log_id}/retry",
    status_code=202,
    response_model=RetryResponse,
    summary="Manually retry a dead delivery",
    description=(
        "Re-enqueues a `dead` delivery log for another `deliver_webhook` attempt. "
        "Returns 400 if the delivery is not in `dead` status."
    ),
    response_description="Confirmation that the delivery was re-queued.",
    responses={
        202: {"content": {"application/json": {"example": RETRY_RESPONSE_EXAMPLE}}},
        400: {
            "description": "Delivery is not in dead status.",
            "content": {"application/json": {"example": BAD_REQUEST_EXAMPLE}},
        },
        404: {
            "description": "Delivery log not found.",
            "content": {"application/json": {"example": NOT_FOUND_EXAMPLE}},
        },
    },
)
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
