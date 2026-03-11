"""unit tests for structured json logging configuration - phase 6.2."""

from __future__ import annotations

import io
import json
import logging

import structlog
from structlog.testing import capture_logs


def test_log_output_is_valid_json() -> None:
    """calling a structlog logger must produce valid json on stdout."""
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(logging.Formatter("%(message)s"))

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )

    root = logging.getLogger()
    original_handlers = root.handlers[:]
    root.handlers = [handler]
    root.setLevel(logging.DEBUG)

    try:
        structlog.get_logger("test").info("hello world")
        output = buffer.getvalue().strip()
        assert output, "no log output produced"
        parsed = json.loads(output)
        assert parsed["event"] == "hello world"
        assert "timestamp" in parsed
        assert "level" in parsed
    finally:
        root.handlers = original_handlers
        structlog.reset_defaults()


def test_log_entry_includes_all_required_fields() -> None:
    """log entries must carry timestamp, level, logger name, and event."""
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(logging.Formatter("%(message)s"))

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )

    root = logging.getLogger()
    original_handlers = root.handlers[:]
    root.handlers = [handler]
    root.setLevel(logging.DEBUG)

    try:
        structlog.get_logger("mylogger").warning("something happened", key="val")
        output = buffer.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["event"] == "something happened"
        assert parsed["level"] == "warning"
        assert parsed["logger"] == "mylogger"
        assert parsed["key"] == "val"
        assert "timestamp" in parsed
    finally:
        root.handlers = original_handlers
        structlog.reset_defaults()


def test_request_id_appears_in_log_when_bound() -> None:
    """request_id bound via contextvars must appear in captured log entries."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id="test-req-id-123")

    try:
        with capture_logs(processors=[structlog.contextvars.merge_contextvars]) as captured:
            structlog.get_logger().info("processing")

        assert len(captured) == 1
        assert captured[0]["request_id"] == "test-req-id-123"
        assert captured[0]["event"] == "processing"
    finally:
        structlog.contextvars.clear_contextvars()
