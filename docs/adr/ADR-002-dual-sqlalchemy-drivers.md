# ADR-002: Dual SQLAlchemy Drivers — asyncpg for FastAPI, psycopg2 for Celery

**Date:** 2025-01-15  
**Status:** Accepted  
**Deciders:** Backend team

---

## Context

The service has two distinct database consumers with conflicting requirements:

- **FastAPI request handlers** run inside an `asyncio` event loop. They require a non-blocking async database driver to avoid starving the event loop.
- **Celery tasks** run in a standard synchronous Python process (no event loop). They cannot use an async driver without significant workaround (running a new event loop per task, which is error-prone and slow).

---

## Decision

We use **two separate SQLAlchemy engines and session factories**:

| Consumer | Driver | SQLAlchemy API | URL prefix |
|---|---|---|---|
| FastAPI routes | `asyncpg` | `create_async_engine` + `async_sessionmaker` | `postgresql+asyncpg://` |
| Celery tasks | `psycopg2-binary` | `create_engine` + `sessionmaker` | `postgresql+psycopg2://` |

Both point to the same PostgreSQL database. The session factories are defined in `app/db/session.py`:

```python
# async — FastAPI
engine = create_async_engine(settings.DATABASE_URL, ...)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, ...)

# sync — Celery
_sync_engine = create_engine(settings.SYNC_DATABASE_URL, ...)
SyncSession = sessionmaker(bind=_sync_engine, ...)
```

---

## Reasons

- `asyncpg` cannot be called from a synchronous context without wrapping it in a new event loop, which is brittle and adds latency.
- `psycopg2` is fully synchronous and integrates seamlessly with Celery's worker process model.
- SQLAlchemy 2.0's async layer is a thin wrapper around the sync ORM; the model definitions (`app/db/models.py`) are shared between both engines.
- `expire_on_commit=False` is set on the async session factory to prevent lazy-load errors when accessing ORM attributes after a commit in an async context.

---

## Consequences

- Two environment variables are required: `DATABASE_URL` (async) and `SYNC_DATABASE_URL` (sync).
- A `@field_validator` on `Settings.DATABASE_URL` enforces the `postgresql+asyncpg://` prefix, catching misconfiguration at startup.
- Integration tests patch `app.tasks.fanout.SyncSession` and `app.tasks.delivery.SyncSession` with a `psycopg2`-backed `sessionmaker` pointing at the test database.
- Any migration to a different async driver (e.g. `psycopg3`) requires updating only `DATABASE_URL` and the `asyncpg` dependency.
