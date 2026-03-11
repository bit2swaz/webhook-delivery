"""async sqlalchemy engine, session factory, and sync session for celery."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# ---------------------------------------------------------------------------
# async engine - used by fastapi request handlers
# ---------------------------------------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

# async session factory - expire_on_commit=False avoids lazy-load errors
# after a commit in async context
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """fastapi dependency that yields an async db session per request."""
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# sync engine - used only by celery tasks (no event loop)
# ---------------------------------------------------------------------------
_sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    pool_pre_ping=True,
)

SyncSession: sessionmaker = sessionmaker(  # type: ignore[type-arg]
    bind=_sync_engine,
    autocommit=False,
    autoflush=False,
)
