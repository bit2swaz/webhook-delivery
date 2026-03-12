"""reusable openapi request/response examples for swagger ui and redoc.

import the dict constants from this module and pass them to ``openapi_examples``
on ``Body()`` parameters or inline in route ``responses=`` dicts.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# subscriber examples
# ---------------------------------------------------------------------------

SUBSCRIBER_CREATE_EXAMPLES: dict[str, object] = {
    "full": {
        "summary": "Subscriber with signing secret",
        "description": (
            "Creates a subscriber that listens only for `order.created` events "
            "and verifies the HMAC-SHA256 signature header."
        ),
        "value": {
            "name": "order-service",
            "url": "https://api.example.com/webhooks/orders",
            "secret": "s3cr3t-hmac-key",
            "event_types": ["order.created", "order.cancelled"],
            "enabled": True,
        },
    },
    "wildcard": {
        "summary": "Wildcard subscriber (all events)",
        "description": (
            "An empty `event_types` list means this subscriber receives "
            "every event regardless of type."
        ),
        "value": {
            "name": "audit-logger",
            "url": "https://audit.example.com/ingest",
            "secret": None,
            "event_types": [],
            "enabled": True,
        },
    },
}

SUBSCRIBER_UPDATE_EXAMPLES: dict[str, object] = {
    "disable": {
        "summary": "Disable a subscriber",
        "value": {"enabled": False},
    },
    "rotate_secret": {
        "summary": "Rotate the signing secret",
        "value": {"secret": "new-hmac-secret-after-rotation"},
    },
}

SUBSCRIBER_READ_EXAMPLE: dict[str, object] = {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "order-service",
    "url": "https://api.example.com/webhooks/orders",
    "secret": None,
    "event_types": ["order.created"],
    "enabled": True,
    "created_at": "2025-01-15T10:00:00Z",
}

# ---------------------------------------------------------------------------
# event examples
# ---------------------------------------------------------------------------

EVENT_CREATE_EXAMPLES: dict[str, object] = {
    "order_created": {
        "summary": "order.created event",
        "value": {
            "event_type": "order.created",
            "payload": {
                "order_id": "ord_12345",
                "customer_id": "cust_987",
                "total": 149.99,
                "currency": "USD",
            },
        },
    },
    "payment_done": {
        "summary": "payment.done event",
        "value": {
            "event_type": "payment.done",
            "payload": {
                "payment_id": "pay_abc",
                "order_id": "ord_12345",
                "amount": 149.99,
            },
        },
    },
}

EVENT_INGEST_RESPONSE_EXAMPLE: dict[str, object] = {
    "event_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "status": "queued",
}

EVENT_DETAIL_RESPONSE_EXAMPLE: dict[str, object] = {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "event_type": "order.created",
    "payload": {"order_id": "ord_12345", "total": 149.99},
    "received_at": "2025-01-15T10:05:00Z",
    "deliveries": [
        {
            "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
            "status": "success",
            "attempt_number": 1,
            "attempted_at": "2025-01-15T10:05:01Z",
        }
    ],
}

# ---------------------------------------------------------------------------
# delivery log examples
# ---------------------------------------------------------------------------

DELIVERY_LOG_READ_EXAMPLE: dict[str, object] = {
    "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "event_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "subscriber_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "attempt_number": 2,
    "status": "failed",
    "response_status": 503,
    "response_body": None,
    "duration_ms": 312,
    "attempted_at": "2025-01-15T10:05:30Z",
    "next_retry_at": "2025-01-15T10:10:30Z",
}

RETRY_RESPONSE_EXAMPLE: dict[str, object] = {
    "status": "requeued",
}

# ---------------------------------------------------------------------------
# auth examples
# ---------------------------------------------------------------------------

_EXAMPLE_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzZXJ2aWNlIiwiZXhwIjoxNzM2OTM2MDAwfQ.abc123"
)

TOKEN_RESPONSE_EXAMPLE: dict[str, object] = {
    "access_token": _EXAMPLE_JWT,
    "token_type": "bearer",
}

# ---------------------------------------------------------------------------
# common error response shapes
# ---------------------------------------------------------------------------

NOT_FOUND_EXAMPLE: dict[str, object] = {"detail": "subscriber not found"}
BAD_REQUEST_EXAMPLE: dict[str, object] = {"detail": "only dead deliveries can be retried"}
UNAUTHORIZED_EXAMPLE: dict[str, object] = {"detail": "could not validate credentials"}
