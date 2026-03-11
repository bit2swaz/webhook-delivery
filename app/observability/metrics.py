"""prometheus counters and histograms for webhook delivery outcomes."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# ---------------------------------------------------------------------------
# metric definitions
# ---------------------------------------------------------------------------

DELIVERIES_SUCCESS: Counter = Counter(
    "deliveries_success_total",
    "total successful webhook deliveries",
    ["subscriber_id"],
)

DELIVERIES_FAILED: Counter = Counter(
    "deliveries_failed_total",
    "total failed webhook delivery attempts (before dead)",
    ["subscriber_id"],
)

DELIVERIES_DEAD: Counter = Counter(
    "deliveries_dead_total",
    "total webhook deliveries permanently failed (dead letter)",
    ["subscriber_id"],
)

# custom buckets covering fast (50ms) through very slow (10s) webhook responses
_DURATION_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf"))

DELIVERY_DURATION: Histogram = Histogram(
    "webhook_delivery_duration_seconds",
    "end-to-end duration of a single webhook delivery attempt",
    ["subscriber_id"],
    buckets=_DURATION_BUCKETS,
)

# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------


def record_success(subscriber_id: str) -> None:
    """increment the success counter for the given subscriber."""
    DELIVERIES_SUCCESS.labels(subscriber_id=subscriber_id).inc()


def record_failed(subscriber_id: str) -> None:
    """increment the failed counter for the given subscriber."""
    DELIVERIES_FAILED.labels(subscriber_id=subscriber_id).inc()


def record_dead(subscriber_id: str) -> None:
    """increment the dead-letter counter for the given subscriber."""
    DELIVERIES_DEAD.labels(subscriber_id=subscriber_id).inc()


def record_duration(subscriber_id: str, duration_ms: int) -> None:
    """observe a delivery duration (milliseconds) in the histogram.

    converts milliseconds to seconds before observing.
    """
    DELIVERY_DURATION.labels(subscriber_id=subscriber_id).observe(duration_ms / 1000)
