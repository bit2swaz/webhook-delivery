"""shared factories for generating test data."""

from __future__ import annotations

import factory

from app.db.schemas import EventCreate, SubscriberCreate


class SubscriberFactory(factory.Factory):
    """factory for SubscriberCreate schema instances."""

    class Meta:
        model = SubscriberCreate

    name: str = factory.Sequence(lambda n: f"subscriber-{n}")
    url: str = factory.Sequence(lambda n: f"https://sub-{n}.example.com/webhook")
    secret = None
    event_types: list[str] = factory.LazyFunction(list)
    enabled: bool = True


class EventFactory(factory.Factory):
    """factory for EventCreate schema instances."""

    class Meta:
        model = EventCreate

    event_type: str = factory.Sequence(lambda n: f"event.type.{n}")
    payload: dict = factory.LazyFunction(lambda: {"key": "value"})  # type: ignore[type-arg]
