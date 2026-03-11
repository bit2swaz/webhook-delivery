"""shared factories for generating test data."""

from __future__ import annotations

import factory

from app.db.schemas import SubscriberCreate


class SubscriberFactory(factory.Factory):
    """factory for SubscriberCreate schema instances."""

    class Meta:
        model = SubscriberCreate

    name: str = factory.Sequence(lambda n: f"subscriber-{n}")
    url: str = factory.Sequence(lambda n: f"https://sub-{n}.example.com/webhook")
    secret = None
    event_types: list[str] = factory.LazyFunction(list)
    enabled: bool = True
