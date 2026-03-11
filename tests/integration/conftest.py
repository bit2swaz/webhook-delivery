"""integration test fixtures - real postgres via webhooks_test database."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models import Base
from app.db.session import get_db
from app.main import app


@pytest_asyncio.fixture
async def test_engine():
    """async engine pointed at webhooks_test; ensures all tables exist."""
    engine = create_async_engine(settings.TEST_DATABASE_URL, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """standalone session for seeding test data directly (not shared with app)."""
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def authed_client(test_engine):
    """httpx client with jwt auth; overrides get_db to use test db.

    truncates subscriber/event/delivery tables after each test.
    """
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": "test-service"})
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.headers["Authorization"] = f"Bearer {token}"
        yield client

    app.dependency_overrides.pop(get_db, None)
    async with test_engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE TABLE delivery_log, events, subscribers RESTART IDENTITY CASCADE")
        )
