"""unit tests for sqlalchemy orm models (phase 1.1 - red first)."""

from __future__ import annotations

import uuid

import pytest

from app.db.models import Base, DeliveryLog, Event, Subscriber


class TestSubscriberModel:
    """tests for the Subscriber orm model."""

    def test_subscriber_table_name(self) -> None:
        assert Subscriber.__tablename__ == "subscribers"

    def test_subscriber_instantiation(self) -> None:
        sub = Subscriber(name="acme", url="https://acme.example.com/hook")
        assert sub.name == "acme"
        assert sub.url == "https://acme.example.com/hook"

    def test_subscriber_enabled_default(self) -> None:
        sub = Subscriber(name="acme", url="https://acme.example.com/hook")
        # enabled defaults to True at the db level; python-level default should also be True
        assert sub.enabled is True or sub.enabled is None

    def test_subscriber_event_types_column_exists(self) -> None:
        """event_types column must exist on the mapper."""
        columns = {c.key for c in Subscriber.__mapper__.column_attrs}
        assert "event_types" in columns

    def test_subscriber_id_is_uuid_type(self) -> None:
        col = Subscriber.__table__.c["id"]
        # postgresql UUID type
        assert "UUID" in type(col.type).__name__.upper()

    def test_subscriber_has_created_at(self) -> None:
        columns = {c.key for c in Subscriber.__mapper__.column_attrs}
        assert "created_at" in columns


class TestEventModel:
    """tests for the Event orm model."""

    def test_event_table_name(self) -> None:
        assert Event.__tablename__ == "events"

    def test_event_instantiation(self) -> None:
        evt = Event(event_type="order.created", payload={"order_id": "123"})
        assert evt.event_type == "order.created"
        assert evt.payload == {"order_id": "123"}

    def test_event_id_is_uuid_type(self) -> None:
        col = Event.__table__.c["id"]
        assert "UUID" in type(col.type).__name__.upper()

    def test_event_payload_is_jsonb(self) -> None:
        col = Event.__table__.c["payload"]
        assert "JSONB" in type(col.type).__name__.upper()

    def test_event_has_received_at(self) -> None:
        columns = {c.key for c in Event.__mapper__.column_attrs}
        assert "received_at" in columns


class TestDeliveryLogModel:
    """tests for the DeliveryLog orm model."""

    def test_delivery_log_table_name(self) -> None:
        assert DeliveryLog.__tablename__ == "delivery_log"

    def test_delivery_log_instantiation(self) -> None:
        event_id = uuid.uuid4()
        subscriber_id = uuid.uuid4()
        log = DeliveryLog(event_id=event_id, subscriber_id=subscriber_id)
        assert log.event_id == event_id
        assert log.subscriber_id == subscriber_id

    def test_delivery_log_status_default(self) -> None:
        log = DeliveryLog()
        # status default is "pending" (may be set at python level or db level)
        assert log.status == "pending" or log.status is None

    def test_delivery_log_attempt_number_default(self) -> None:
        log = DeliveryLog()
        assert log.attempt_number == 1 or log.attempt_number is None

    def test_delivery_log_has_all_columns(self) -> None:
        expected = {
            "id",
            "event_id",
            "subscriber_id",
            "attempt_number",
            "status",
            "response_status",
            "response_body",
            "duration_ms",
            "attempted_at",
            "next_retry_at",
        }
        columns = {c.key for c in DeliveryLog.__mapper__.column_attrs}
        assert expected.issubset(columns)

    def test_delivery_log_fk_to_events(self) -> None:
        fk_cols = {fk.column.table.name for fk in DeliveryLog.__table__.foreign_keys}
        assert "events" in fk_cols

    def test_delivery_log_fk_to_subscribers(self) -> None:
        fk_cols = {fk.column.table.name for fk in DeliveryLog.__table__.foreign_keys}
        assert "subscribers" in fk_cols


class TestBaseMetadata:
    """tests for the declarative base and metadata."""

    def test_all_tables_registered(self) -> None:
        assert "subscribers" in Base.metadata.tables
        assert "events" in Base.metadata.tables
        assert "delivery_log" in Base.metadata.tables

    def test_base_has_async_attrs(self) -> None:
        from sqlalchemy.ext.asyncio import AsyncAttrs

        assert issubclass(Subscriber, AsyncAttrs)
        assert issubclass(Event, AsyncAttrs)
        assert issubclass(DeliveryLog, AsyncAttrs)


@pytest.mark.parametrize(
    "status",
    ["pending", "delivering", "success", "failed", "dead"],
)
def test_delivery_status_values(status: str) -> None:
    """all valid status strings can be set on a delivery log instance."""
    log = DeliveryLog(status=status)
    assert log.status == status
