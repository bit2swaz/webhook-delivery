"""request id and access logging middleware."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

REQUEST_ID_CTX: ContextVar[str] = ContextVar("request_id", default="")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """attach a unique request id to every request/response cycle.

    if the incoming request contains an X-Request-ID header, the same value is
    used; otherwise a fresh uuid4 is generated. the id is:

    - stored in REQUEST_ID_CTX for any downstream code that needs it
    - bound to structlog context vars so every log line carries request_id
    - echoed back in the X-Request-ID response header

    an access log line (method, path, status_code, duration_ms) is emitted
    after each request completes.
    """

    def __init__(self, app: ASGIApp) -> None:
        """initialise middleware with the wrapped asgi application.

        Args:
            app: the next asgi application in the middleware stack.
        """
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """process a single request: bind request id and emit an access log.

        Args:
            request: the incoming starlette request.
            call_next: the next handler in the middleware chain.

        Returns:
            the response with X-Request-ID header set.
        """
        structlog.contextvars.clear_contextvars()

        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        REQUEST_ID_CTX.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        log = structlog.get_logger(__name__)
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Request-ID"] = request_id
        return response
