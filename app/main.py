"""fastapi application entry point.

bootstraps the app, registers routers, middleware, and lifecycle events.
"""

from __future__ import annotations

import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.middleware import RequestIDMiddleware
from app.api.routes import auth, deliveries, events, subscribers
from app.core.logging import configure_logging


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """catch-all exception handler - returns a safe 500 json body.

    logs the full traceback server-side but never leaks internal detail
    to the caller.

    Args:
        request: the starlette request that triggered the exception.
        exc: the unhandled exception.

    Returns:
        a json response with status 500 and a generic error message.
    """
    log = structlog.get_logger(__name__)
    log.error(
        "unhandled exception",
        exc_info=exc,
        traceback=traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """manage application startup and shutdown events.

    Args:
        app: the fastapi application instance.

    Yields:
        nothing - control returns to fastapi during the app lifetime.
    """
    configure_logging()
    yield
    # shutdown


def create_app() -> FastAPI:
    """construct and configure the fastapi application.

    Returns:
        a fully configured FastAPI instance.
    """
    application = FastAPI(
        title="webhook delivery service",
        description=(
            "accepts incoming events via rest api, fans out to registered "
            "subscriber endpoints, retries failed deliveries with exponential "
            "backoff, and exposes full observability via prometheus."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(RequestIDMiddleware)
    application.add_exception_handler(Exception, unhandled_exception_handler)

    @application.get(
        "/health",
        tags=["ops"],
        summary="health check",
        description="returns the liveness status of the api. does not check db or redis.",
    )
    async def health() -> JSONResponse:
        """lightweight liveness probe.

        Returns:
            json response with status ok and http 200.
        """
        return JSONResponse({"status": "ok"})

    application.include_router(auth.router, prefix="/auth", tags=["auth"])
    application.include_router(subscribers.router, prefix="/subscribers", tags=["subscribers"])
    application.include_router(events.router)
    application.include_router(deliveries.router)

    return application


app: FastAPI = create_app()
