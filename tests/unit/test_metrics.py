"""unit tests for prometheus metrics helpers.

tests are isolated using unittest.mock.patch so the global registry is
never touched and counter state does not bleed between test runs.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.observability.metrics import (
    record_dead,
    record_duration,
    record_failed,
    record_success,
)

# ---------------------------------------------------------------------------
# record_success
# ---------------------------------------------------------------------------


def test_record_success_increments_counter() -> None:
    """record_success calls .labels(subscriber_id=...).inc() on DELIVERIES_SUCCESS."""
    with patch("app.observability.metrics.DELIVERIES_SUCCESS") as mock_counter:
        record_success("sub-001")

    mock_counter.labels.assert_called_once_with(subscriber_id="sub-001")
    mock_counter.labels.return_value.inc.assert_called_once()


def test_record_success_does_not_touch_failed_or_dead() -> None:
    """record_success must not increment the failed or dead counters."""
    with (
        patch("app.observability.metrics.DELIVERIES_FAILED") as mock_failed,
        patch("app.observability.metrics.DELIVERIES_DEAD") as mock_dead,
        patch("app.observability.metrics.DELIVERIES_SUCCESS"),
    ):
        record_success("sub-001")

    mock_failed.labels.assert_not_called()
    mock_dead.labels.assert_not_called()


# ---------------------------------------------------------------------------
# record_failed
# ---------------------------------------------------------------------------


def test_record_failed_increments_counter() -> None:
    """record_failed calls .labels(subscriber_id=...).inc() on DELIVERIES_FAILED."""
    with patch("app.observability.metrics.DELIVERIES_FAILED") as mock_counter:
        record_failed("sub-002")

    mock_counter.labels.assert_called_once_with(subscriber_id="sub-002")
    mock_counter.labels.return_value.inc.assert_called_once()


# ---------------------------------------------------------------------------
# record_dead
# ---------------------------------------------------------------------------


def test_record_dead_increments_counter() -> None:
    """record_dead calls .labels(subscriber_id=...).inc() on DELIVERIES_DEAD."""
    with patch("app.observability.metrics.DELIVERIES_DEAD") as mock_counter:
        record_dead("sub-003")

    mock_counter.labels.assert_called_once_with(subscriber_id="sub-003")
    mock_counter.labels.return_value.inc.assert_called_once()


# ---------------------------------------------------------------------------
# record_duration
# ---------------------------------------------------------------------------


def test_record_duration_observes_histogram() -> None:
    """record_duration calls .labels(subscriber_id=...).observe(seconds) on DELIVERY_DURATION."""
    with patch("app.observability.metrics.DELIVERY_DURATION") as mock_hist:
        record_duration("sub-004", duration_ms=250)

    mock_hist.labels.assert_called_once_with(subscriber_id="sub-004")
    mock_hist.labels.return_value.observe.assert_called_once_with(pytest.approx(0.25))


def test_record_duration_converts_ms_to_seconds() -> None:
    """record_duration converts milliseconds to seconds before observing."""
    with patch("app.observability.metrics.DELIVERY_DURATION") as mock_hist:
        record_duration("sub-004", duration_ms=1000)

    observed = mock_hist.labels.return_value.observe.call_args[0][0]
    assert observed == pytest.approx(1.0)


def test_record_duration_zero_ms() -> None:
    """record_duration handles 0 ms without error."""
    with patch("app.observability.metrics.DELIVERY_DURATION") as mock_hist:
        record_duration("sub-004", duration_ms=0)

    mock_hist.labels.return_value.observe.assert_called_once_with(pytest.approx(0.0))
