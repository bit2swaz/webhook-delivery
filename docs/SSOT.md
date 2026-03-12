# Webhook Delivery Service (Python)

## Overview
A production-grade webhook delivery system in Python. Accepts incoming events via REST API, fans out to registered subscriber endpoints, retries failed deliveries with exponential backoff, tracks delivery status per subscriber, and exposes full observability via Prometheus. Async-first with FastAPI + Celery.

## Stack
| Layer | Tech |
|---|---|
| Language | Python 3.12 |
| Framework | FastAPI |
| Task Queue | Celery |
| Broker | Redis 7 |
| Result Backend | Redis |
| Database | PostgreSQL (subscribers, events, delivery log) |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Auth | JWT (python-jose) |
| Observability | Prometheus (prometheus-fastapi-instrumentator) |
| HTTP Client | httpx (async) |
| Containerization | Docker + Docker Compose |
| Testing | pytest + pytest-asyncio + httpx |

## Architecture

```mermaid
flowchart LR
    ES([External Service]) -->|"POST /events"| API[FastAPI]
    API -->|fan_out_event| Q[(Redis Broker)]
    Q -->|consume| W[Celery Worker]
    W -->|"httpx POST"| SUB([Subscribers])
    API <-->|"async SQL"| DB[(PostgreSQL)]
    W <-->|"sync SQL"| DB
    API -.->|"/metrics"| PROM([Prometheus])
```

## Delivery State Machine

```mermaid
stateDiagram-v2
    [*] --> PENDING : DeliveryLog created by fan_out_event
    PENDING --> DELIVERING : task dispatched
    DELIVERING --> SUCCESS : HTTP 2xx
    DELIVERING --> FAILED : non-2xx / timeout
    FAILED --> DELIVERING : retry (30s→5m→30m→2h→8h)
    FAILED --> DEAD : max attempts exhausted
    SUCCESS --> [*]
    DEAD --> [*]
```

## Directory Structure

```
webhook-delivery/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── events.py        # POST /events (ingest + fan-out)
│   │   │   ├── subscribers.py   # CRUD /subscribers
│   │   │   ├── deliveries.py    # GET /deliveries (status + logs)
│   │   │   └── auth.py          # POST /auth/token
│   │   ├── deps.py              # FastAPI dependencies (DB session, JWT)
│   │   └── middleware.py        # Request ID, logging
│   ├── core/
│   │   ├── config.py            # Settings via pydantic-settings
│   │   ├── security.py          # JWT encode/decode
│   │   └── logging.py           # Structured JSON logging
│   ├── db/
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── schemas.py           # Pydantic schemas (request/response)
│   │   └── session.py           # Async engine + session factory
│   ├── tasks/
│   │   ├── celery_app.py        # Celery instance + Redis broker config
│   │   ├── delivery.py          # deliver_webhook Celery task
│   │   └── fanout.py            # fan_out_event task (creates per-sub tasks)
│   ├── services/
│   │   ├── subscriber_service.py
│   │   └── delivery_service.py  # Delivery log business logic
│   ├── observability/
│   │   └── metrics.py           # Prometheus counters + histograms
│   └── main.py                  # FastAPI app bootstrap
├── alembic/
│   └── versions/                # DB migrations
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   └── docker-compose.yml
├── tests/
│   ├── test_events.py
│   ├── test_delivery.py
│   └── test_subscribers.py
├── .env.example
└── README.md
```

## Database Schema

```sql
-- subscribers: who wants to receive webhooks
CREATE TABLE subscribers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    url         TEXT NOT NULL,              -- endpoint to POST to
    secret      TEXT,                       -- HMAC signing secret
    event_types TEXT[] DEFAULT '{}',        -- filter: which events to receive
    enabled     BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- events: incoming events to be delivered
CREATE TABLE events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type  TEXT NOT NULL,              -- e.g. "order.created"
    payload     JSONB NOT NULL,
    received_at TIMESTAMPTZ DEFAULT NOW()
);

-- delivery_log: one row per (event, subscriber) attempt
CREATE TABLE delivery_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID REFERENCES events(id),
    subscriber_id   UUID REFERENCES subscribers(id),
    attempt_number  INTEGER DEFAULT 1,
    status          TEXT DEFAULT 'pending', -- pending/delivering/success/failed/dead
    response_status INTEGER,                -- HTTP status from subscriber
    response_body   TEXT,
    duration_ms     INTEGER,
    attempted_at    TIMESTAMPTZ,
    next_retry_at   TIMESTAMPTZ
);
```

## Core Implementation Details

### 1. Celery App
```python
# app/tasks/celery_app.py
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "webhook-delivery",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.delivery", "app.tasks.fanout"],
)

celery_app.conf.update(
    task_serializer="json",
    result_expires=3600,
    worker_prefetch_multiplier=1,    # fair dispatch
    task_acks_late=True,             # ack after completion, not pickup
    task_reject_on_worker_lost=True, # requeue if worker dies mid-task
)
```

### 2. Fan-out Task
```python
# app/tasks/fanout.py
from celery import shared_task
from app.db.session import SyncSession
from app.db.models import Subscriber, DeliveryLog
from app.tasks.delivery import deliver_webhook

@shared_task
def fan_out_event(event_id: str, event_type: str, payload: dict):
    """Creates one delivery task per matching subscriber."""
    with SyncSession() as db:
        subscribers = db.query(Subscriber).filter(
            Subscriber.enabled == True,
            # Match subscribers that listen to this event type or all events
            (Subscriber.event_types == '{}') |
            Subscriber.event_types.any(event_type)
        ).all()

        for sub in subscribers:
            log = DeliveryLog(
                event_id=event_id,
                subscriber_id=str(sub.id),
                status="pending"
            )
            db.add(log)
            db.flush()

            # Schedule delivery with countdown=0 (immediate)
            deliver_webhook.apply_async(
                args=[str(log.id), str(sub.id), payload],
                countdown=0,
            )
        db.commit()
```

### 3. Delivery Task (with retry logic)
```python
# app/tasks/delivery.py
import httpx
import hmac, hashlib, time
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

# Backoff schedule: 30s, 5m, 30m, 2h, 8h
BACKOFF_SCHEDULE = [30, 300, 1800, 7200, 28800]
MAX_ATTEMPTS = len(BACKOFF_SCHEDULE) + 1

@shared_task(bind=True, max_retries=len(BACKOFF_SCHEDULE))
def deliver_webhook(self, delivery_log_id: str, subscriber_id: str, payload: dict):
    with SyncSession() as db:
        log = db.get(DeliveryLog, delivery_log_id)
        sub = db.get(Subscriber, subscriber_id)

        log.status = "delivering"
        log.attempt_number = self.request.retries + 1
        log.attempted_at = datetime.utcnow()
        db.commit()

    try:
        headers = {"Content-Type": "application/json"}

        # HMAC signature for subscriber verification
        if sub.secret:
            body = json.dumps(payload).encode()
            sig = hmac.new(sub.secret.encode(), body, hashlib.sha256).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={sig}"

        start = time.monotonic()
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(sub.url, json=payload, headers=headers)
        duration_ms = int((time.monotonic() - start) * 1000)

        with SyncSession() as db:
            log = db.get(DeliveryLog, delivery_log_id)
            log.response_status = resp.status_code
            log.duration_ms = duration_ms

            if resp.is_success:
                log.status = "success"
                deliveries_success.labels(subscriber_id=subscriber_id).inc()
            else:
                raise Exception(f"Subscriber returned {resp.status_code}")

            db.commit()

    except Exception as exc:
        attempt = self.request.retries
        deliveries_failed.labels(subscriber_id=subscriber_id).inc()

        try:
            countdown = BACKOFF_SCHEDULE[attempt]
            with SyncSession() as db:
                log = db.get(DeliveryLog, delivery_log_id)
                log.status = "failed"
                log.next_retry_at = datetime.utcnow() + timedelta(seconds=countdown)
                db.commit()

            raise self.retry(exc=exc, countdown=countdown)

        except MaxRetriesExceededError:
            with SyncSession() as db:
                log = db.get(DeliveryLog, delivery_log_id)
                log.status = "dead"
                db.commit()
            deliveries_dead.labels(subscriber_id=subscriber_id).inc()
```

### 4. Event Ingest API
```python
# app/api/routes/events.py
from fastapi import APIRouter, Depends, BackgroundTasks
from app.db.session import get_db
from app.db.models import Event
from app.tasks.fanout import fan_out_event

router = APIRouter(prefix="/events", tags=["events"])

@router.post("/", status_code=202)
async def ingest_event(
    body: EventCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_jwt)
):
    # Persist event
    event = Event(event_type=body.event_type, payload=body.payload)
    db.add(event)
    await db.commit()

    # Async fan-out (non-blocking)
    fan_out_event.delay(str(event.id), body.event_type, body.payload)

    return {"event_id": str(event.id), "status": "queued"}

# Pydantic schema
class EventCreate(BaseModel):
    event_type: str       # e.g. "order.created"
    payload: dict
```

### 5. Prometheus Metrics
```python
# app/observability/metrics.py
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

# Auto-instrument all FastAPI routes (latency, request count)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Custom webhook delivery metrics
deliveries_success = Counter(
    "webhook_deliveries_success_total",
    "Successful webhook deliveries",
    ["subscriber_id"]
)
deliveries_failed = Counter(
    "webhook_deliveries_failed_total",
    "Failed webhook delivery attempts",
    ["subscriber_id"]
)
deliveries_dead = Counter(
    "webhook_deliveries_dead_total",
    "Webhooks that exhausted all retries",
    ["subscriber_id"]
)
delivery_duration = Histogram(
    "webhook_delivery_duration_seconds",
    "HTTP request duration to subscriber endpoint",
    ["subscriber_id"],
    buckets=[.05, .1, .25, .5, 1, 2.5, 5, 10]
)
```

### 6. Docker Compose
```yaml
# docker/docker-compose.yml
version: '3.9'
services:
  api:
    build: { context: ., dockerfile: docker/Dockerfile }
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/webhooks
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      db: { condition: service_healthy }
      redis: { condition: service_healthy }
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  worker:
    build: { context: ., dockerfile: docker/Dockerfile.worker }
    environment:
      - DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/webhooks
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      db: { condition: service_healthy }
      redis: { condition: service_healthy }
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=8
    deploy:
      replicas: 2

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=webhooks
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      retries: 5
    volumes:
      - pg_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports: ["9090:9090"]

volumes:
  pg_data:
```

## API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | /auth/token | none | Issue JWT |
| POST | /subscribers | JWT | Register subscriber (URL + event filters) |
| GET | /subscribers | JWT | List subscribers |
| PUT | /subscribers/:id | JWT | Update subscriber |
| DELETE | /subscribers/:id | JWT | Remove subscriber |
| POST | /events | JWT | Ingest event, trigger fan-out |
| GET | /events/:id | JWT | Event details + delivery status per subscriber |
| GET | /deliveries/:id | JWT | Single delivery attempt log |
| GET | /deliveries/:id/retry | JWT | Manually retry a dead delivery |
| GET | /metrics | none | Prometheus metrics |
| GET | /health | none | API + worker health |

## Environment Variables
```env
PORT=8000
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/webhooks
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your-secret
MAX_DELIVERY_ATTEMPTS=6
```

## Resume Bullet Points (copy-paste ready)
- Built an async webhook delivery system in Python (FastAPI + Celery) that fans out events to registered subscribers with per-subscriber filtering by event type
- Implemented exponential backoff retry schedule (30s → 5m → 30m → 2h → 8h) with dead-letter tracking in PostgreSQL; HMAC-SHA256 request signing for subscriber verification
- Designed PostgreSQL schema (subscribers, events, delivery_log) with Alembic migrations; used async SQLAlchemy for non-blocking DB access in the API layer
- Instrumented FastAPI routes and Celery task outcomes with Prometheus; containerized API + worker as separately scalable Docker services with Docker Compose
