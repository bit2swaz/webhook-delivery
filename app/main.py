"""fastapi application entry point.

bootstraps the app, registers routers, middleware, and lifecycle events.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes import auth, subscribers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """manage application startup and shutdown events.

    Args:
        app: the fastapi application instance.

    Yields:
        nothing - control returns to fastapi during the app lifetime.
    """
    # startup
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

    return application


app: FastAPI = create_app()
