"""root conftest.py - shared pytest fixtures for the entire test suite.

provides:
- async_client: httpx async client wired to the fastapi app (no real db needed)
- settings_override: injects test-safe settings into the di container
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """return a settings instance with test-safe values.

    uses in-memory/local defaults so unit tests never need real infra.

    Returns:
        a Settings instance configured for testing.
    """
    return Settings(
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/webhooks_test",
        SYNC_DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/webhooks_test",
        TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/webhooks_test",
        JWT_SECRET="test-secret-do-not-use-in-production",
        ACCESS_TOKEN_EXPIRE_MINUTES=60,
        MAX_DELIVERY_ATTEMPTS=6,
        RUN_MIGRATIONS_ON_START=False,
    )


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """httpx async client targeting the fastapi app via asgi transport.

    does not require a running server - uses starlette's asgi interface directly.
    each test gets a fresh client; no state leaks between tests.

    Yields:
        an httpx.AsyncClient configured against the app.
    """
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
