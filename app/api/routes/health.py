"""health endpoint - readiness probe with db and redis connectivity checks."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

router = APIRouter(tags=["ops"])


async def _ping_db() -> bool:
    """attempt a SELECT 1 against the database.

    returns true if the query succeeds, false on any exception.
    """
    try:
        engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:
        return False


async def _ping_redis() -> bool:
    """attempt a PING against the redis instance.

    returns true if the ping succeeds, false on any exception.
    """
    try:
        r: aioredis.Redis = aioredis.from_url(settings.REDIS_URL)  # type: ignore[no-untyped-call]
        await r.ping()
        await r.aclose()
        return True
    except Exception:
        return False


@router.get(
    "/health",
    summary="health check",
    description=(
        "readiness probe. pings the database and redis. "
        "returns 200 when all dependencies are healthy, 503 otherwise."
    ),
)
async def health() -> JSONResponse:
    """check liveness of db and redis dependencies.

    returns:
        200 with {status: ok, db: ok, redis: ok} when all healthy.
        503 with {status: degraded, db: ..., redis: ...} when any component fails.
    """
    db_ok = await _ping_db()
    redis_ok = await _ping_redis()

    db_status = "ok" if db_ok else "error"
    redis_status = "ok" if redis_ok else "error"
    overall = "ok" if (db_ok and redis_ok) else "degraded"
    code = 200 if overall == "ok" else 503

    return JSONResponse(
        status_code=code,
        content={"status": overall, "db": db_status, "redis": redis_status},
    )
