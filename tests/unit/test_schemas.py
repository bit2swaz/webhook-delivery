"""unit tests for pydantic schemas (phase 1.4 - red first)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.db.schemas import (
    DeliveryLogRead,
    DeliveryLogSummary,
    EventCreate,
    EventRead,
    SubscriberCreate,
    SubscriberRead,
    SubscriberUpdate,
)


class TestSubscriberCreate:
    """tests for SubscriberCreate schema."""

    def test_valid_subscriber_create(self) -> None:
        sub = SubscriberCreate(name="acme", url="https://acme.example.com/hook")
        assert sub.name == "acme"
        assert str(sub.url) == "https://acme.example.com/hook"

    def test_subscriber_create_requires_name(self) -> None:
        with pytest.raises(ValidationError):
            SubscriberCreate(url="https://acme.example.com/hook")  # type: ignore[call-arg]

    def test_subscriber_create_requires_url(self) -> None:
        with pytest.raises(ValidationError):
            SubscriberCreate(name="acme")  # type: ignore[call-arg]

    def test_subscriber_create_rejects_non_http_url(self) -> None:
        with pytest.raises(ValidationError):
            SubscriberCreate(name="acme", url="ftp://bad.url")

    def test_subscriber_create_event_types_defaults_to_empty(self) -> None:
        sub = SubscriberCreate(name="acme", url="https://acme.example.com/hook")
        assert sub.event_types == []

    def test_subscriber_create_accepts_event_types(self) -> None:
        sub = SubscriberCreate(
            name="acme",
            url="https://acme.example.com/hook",
            event_types=["order.created", "order.updated"],
        )
        assert sub.event_types == ["order.created", "order.updated"]

    def test_subscriber_create_optional_secret(self) -> None:
        sub = SubscriberCreate(
            name="acme",
            url="https://acme.example.com/hook",
            secret="mysecret",
        )
        assert sub.secret == "mysecret"


class TestSubscriberUpdate:
    """tests for SubscriberUpdate schema (all fields optional)."""

    def test_subscriber_update_empty_is_valid(self) -> None:
        upd = SubscriberUpdate()
        assert upd.name is None
        assert upd.url is None

    def test_subscriber_update_partial(self) -> None:
        upd = SubscriberUpdate(name="new name")
        assert upd.name == "new name"
        assert upd.url is None

    def test_subscriber_update_enabled_flag(self) -> None:
        upd = SubscriberUpdate(enabled=False)
        assert upd.enabled is False


class TestSubscriberRead:
    """tests for SubscriberRead schema (orm model -> response)."""

    def test_subscriber_read_from_attributes(self) -> None:
        """schema must be constructable from orm-like attribute access."""
        sub_id = uuid.uuid4()
        now = datetime.now(tz=UTC)

        class FakeOrm:
            id = sub_id
            name = "acme"
            url = "https://acme.example.com/hook"
            secret = None
            event_types: list[str] = []
            enabled = True
            created_at = now

        read = SubscriberRead.model_validate(FakeOrm(), from_attributes=True)
        assert read.id == sub_id
        assert read.name == "acme"

    def test_subscriber_read_has_id(self) -> None:
        sub_id = uuid.uuid4()
        read = SubscriberRead(
            id=sub_id,
            name="acme",
            url="https://example.com",  # type: ignore[arg-type]
            secret=None,
            event_types=[],
            enabled=True,
            created_at=None,
        )
        assert read.id == sub_id


class TestEventCreate:
    """tests for EventCreate schema."""

    def test_valid_event_create(self) -> None:
        evt = EventCreate(event_type="order.created", payload={"order_id": "123"})
        assert evt.event_type == "order.created"
        assert evt.payload == {"order_id": "123"}

    def test_event_create_requires_event_type(self) -> None:
        with pytest.raises(ValidationError):
            EventCreate(payload={"key": "val"})  # type: ignore[call-arg]

    def test_event_create_requires_payload(self) -> None:
        with pytest.raises(ValidationError):
            EventCreate(event_type="order.created")  # type: ignore[call-arg]


class TestEventRead:
    """tests for EventRead schema."""

    def test_event_read_from_attributes(self) -> None:
        evt_id = uuid.uuid4()

        class FakeEvent:
            id = evt_id
            event_type = "order.created"
            payload = {"order_id": "123"}
            received_at = datetime.now(tz=UTC)

        read = EventRead.model_validate(FakeEvent(), from_attributes=True)
        assert read.id == evt_id
        assert read.event_type == "order.created"


class TestDeliveryLogRead:
    """tests for DeliveryLogRead schema."""

    def test_delivery_log_read_has_status(self) -> None:
        log_id = uuid.uuid4()
        log = DeliveryLogRead(
            id=log_id,
            event_id=None,
            subscriber_id=None,
            attempt_number=1,
            status="pending",
            response_status=None,
            response_body=None,
            duration_ms=None,
            attempted_at=None,
            next_retry_at=None,
        )
        assert log.status == "pending"

    def test_delivery_log_read_all_valid_statuses(self) -> None:
        for status in ["pending", "delivering", "success", "failed", "dead"]:
            log = DeliveryLogRead(
                id=uuid.uuid4(),
                event_id=None,
                subscriber_id=None,
                attempt_number=1,
                status=status,
                response_status=None,
                response_body=None,
                duration_ms=None,
                attempted_at=None,
                next_retry_at=None,
            )
            assert log.status == status


class TestDeliveryLogSummary:
    """tests for DeliveryLogSummary schema."""

    def test_summary_fields(self) -> None:
        summary = DeliveryLogSummary(
            id=uuid.uuid4(),
            status="success",
            attempt_number=1,
            attempted_at=None,
        )
        assert summary.status == "success"
        assert summary.attempt_number == 1
