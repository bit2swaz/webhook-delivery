"""structured json logging configuration using structlog."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging() -> None:
    """configure structlog for structured json output.

    sets up stdlib logging to output raw messages to stdout (structlog
    renders them to json), then configures structlog with a processor chain
    that:

    - merges context variables (e.g. request_id) into every log entry
    - adds log level and logger name
    - adds an iso 8601 utc timestamp
    - renders exceptions as dicts (no multiline traceback noise)
    - serialises the entire event dict to json

    should be called once at application startup via the fastapi lifespan.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
