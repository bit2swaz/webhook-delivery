"""unit tests for session factory (phase 1.2 - red first)."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import AsyncSessionLocal, SyncSession, engine, get_db


class TestAsyncEngine:
    """tests for the async sqlalchemy engine."""

    def test_engine_is_async(self) -> None:
        assert isinstance(engine, AsyncEngine)

    def test_engine_uses_asyncpg_dialect(self) -> None:
        assert engine.dialect.name == "postgresql"
        # driver name should contain asyncpg
        assert "asyncpg" in engine.dialect.driver


class TestAsyncSessionLocal:
    """tests for the async session factory."""

    def test_session_local_is_async_sessionmaker(self) -> None:
        assert isinstance(AsyncSessionLocal, async_sessionmaker)

    def test_session_local_expire_on_commit_false(self) -> None:
        # expire_on_commit=False prevents attribute expiry after commit
        assert AsyncSessionLocal.kw.get("expire_on_commit") is False


class TestGetDb:
    """tests for the get_db async generator."""

    def test_get_db_is_async_generator_function(self) -> None:
        import inspect

        assert inspect.isasyncgenfunction(get_db)

    async def test_get_db_yields_async_session(self) -> None:
        gen = get_db()
        assert isinstance(gen, AsyncGenerator)
        # we do not actually open a db connection here - just check it's a generator
        await gen.aclose()


class TestSyncSession:
    """tests for the sync session factory (used by celery tasks)."""

    def test_sync_session_is_sessionmaker(self) -> None:
        assert isinstance(SyncSession, sessionmaker)

    def test_sync_session_produces_session(self) -> None:
        # calling SyncSession() should return a Session instance without
        # actually opening a connection (lazy connection)
        with SyncSession() as sess:
            assert isinstance(sess, Session)
