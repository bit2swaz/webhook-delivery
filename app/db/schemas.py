"""pydantic v2 request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# subscriber schemas
# ---------------------------------------------------------------------------


class SubscriberBase(BaseModel):
    """shared subscriber fields."""

    name: str
    url: AnyHttpUrl
    secret: str | None = None
    event_types: list[str] = Field(default_factory=list)
    enabled: bool = True


class SubscriberCreate(SubscriberBase):
    """payload to create a new subscriber."""


class SubscriberUpdate(BaseModel):
    """partial update payload - all fields optional."""

    name: str | None = None
    url: AnyHttpUrl | None = None
    secret: str | None = None
    event_types: list[str] | None = None
    enabled: bool | None = None


class SubscriberRead(SubscriberBase):
    """full subscriber representation returned from api."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# event schemas
# ---------------------------------------------------------------------------


class EventCreate(BaseModel):
    """payload to ingest a new event."""

    event_type: str
    payload: dict  # type: ignore[type-arg]


class EventRead(BaseModel):
    """full event representation returned from api."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    payload: dict  # type: ignore[type-arg]
    received_at: datetime | None = None


# ---------------------------------------------------------------------------
# delivery log schemas
# ---------------------------------------------------------------------------


class DeliveryLogRead(BaseModel):
    """full delivery log row returned from api."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID | None = None
    subscriber_id: uuid.UUID | None = None
    attempt_number: int = 1
    status: str
    response_status: int | None = None
    response_body: str | None = None
    duration_ms: int | None = None
    attempted_at: datetime | None = None
    next_retry_at: datetime | None = None


class DeliveryLogSummary(BaseModel):
    """condensed delivery log for list responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    attempt_number: int
    attempted_at: datetime | None = None


# ---------------------------------------------------------------------------
# auth schemas
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    """response body returned by POST /auth/token."""

    access_token: str
    token_type: str = "bearer"
