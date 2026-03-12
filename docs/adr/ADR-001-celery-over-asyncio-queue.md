# ADR-001: Celery over a Pure-Asyncio Task Queue

**Date:** 2025-01-15  
**Status:** Accepted  
**Deciders:** Backend team

---

## Context

Webhook delivery requires reliable, retriable, background task execution. Two broad options were considered:

1. **Celery** — battle-tested distributed task queue backed by Redis (or RabbitMQ), with a rich feature set including exponential backoff, dead-letter semantics, beat scheduler, canvas primitives, and mature monitoring tools (Flower, Prometheus exporter).

2. **Pure-asyncio queue** — e.g. `arq`, `taskiq`, or a hand-rolled `asyncio.Queue` consumer. Would integrate naturally with FastAPI's async event loop and avoid the `asyncio`/`threading` boundary.

---

## Decision

We chose **Celery** with Redis as broker and result backend.

---

## Reasons

| Criterion | Celery | Pure-asyncio |
|---|---|---|
| Retry + backoff | Built-in (`max_retries`, `countdown`) | Hand-rolled |
| Dead-letter semantics | `MaxRetriesExceededError` pattern | Hand-rolled |
| Worker scaling | Separate `celery worker` processes | Separate async services or threads |
| Monitoring | Flower, Celery events, Prometheus | Varies by library |
| Ecosystem maturity | ~15 years, wide adoption | Relatively newer |
| Operational familiarity | High in Python shops | Lower |

The primary downside of Celery is that worker tasks run in a synchronous process pool, which means we cannot reuse the `asyncpg`-backed async session from FastAPI. This is mitigated by the dual-driver decision (see ADR-002).

---

## Consequences

- Celery workers run as a separate container (`Dockerfile.worker`).
- Tasks use `psycopg2` (sync) for database I/O — see ADR-002.
- Celery configuration is centralised in `app/tasks/celery_app.py`.
- `task_acks_late=True` and `task_reject_on_worker_lost=True` ensure at-least-once delivery semantics.
- `worker_prefetch_multiplier=1` gives fair task dispatch and prevents one slow worker from monopolising the queue.
