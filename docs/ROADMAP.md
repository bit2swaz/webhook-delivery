# Webhook Delivery Service — Development Roadmap

> **Methodology:** Test-Driven Development (TDD) throughout. Every feature is written in Red → Green → Refactor cycles. No production code is merged without a corresponding test. Phases are sequential; mini-phases within each phase can partially overlap but must be completed before moving to the next top-level phase.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| 🔴 | Write failing test first (Red) |
| 🟢 | Make test pass (Green) |
| 🔵 | Refactor / clean up (Blue) |
| 📋 | Planning / scaffolding task |
| 🐳 | Docker / infra task |
| 📝 | Documentation task |
| ✅ | Completion checkpoint |

---

## Phase 0 — Project Foundation & Dev Environment

> **Goal:** A runnable, empty skeleton with all tooling wired up, dev infra containerized, and CI skeleton in place. Zero application logic — just scaffolding.

### 0.1 — Repository & Python Environment
- [ ] 📋 Initialize Git repository, create `.gitignore` (Python, Docker, env files)
- [ ] 📋 Pin Python 3.12 via `.python-version` (pyenv) or `runtime.txt`
- [ ] 📋 Create virtual environment (`python -m venv .venv`)
- [ ] 📋 Create `requirements.txt` (prod) and `requirements-dev.txt` (test/lint)
  ```
  # requirements.txt
  fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic,
  celery[redis], redis, httpx, python-jose[cryptography], passlib[bcrypt],
  pydantic-settings, prometheus-client, prometheus-fastapi-instrumentator,
  psycopg2-binary (sync driver for Celery worker)

  # requirements-dev.txt
  pytest, pytest-asyncio, pytest-cov, httpx, factory-boy,
  ruff, mypy, pre-commit, respx (mock httpx)
  ```
- [ ] 📋 Configure `ruff` (linter + formatter) via `pyproject.toml`
- [ ] 📋 Configure `mypy` strict mode in `pyproject.toml`
- [ ] 📋 Set up `pre-commit` hooks (ruff, mypy, trailing whitespace)

### 0.2 — Directory Skeleton
- [ ] 📋 Scaffold full directory tree per SSOT spec (empty `__init__.py` files)
  ```
  app/, app/api/, app/api/routes/, app/core/, app/db/,
  app/tasks/, app/services/, app/observability/,
  alembic/, docker/, tests/
  ```
- [ ] 📋 Create placeholder module files (no logic, just module docstrings)
- [ ] 📋 Create `app/main.py` with bare `FastAPI()` instance (no routes)

### 0.3 — Dev Infrastructure (Docker Compose)
- [ ] 🐳 Create `docker/docker-compose.dev.yml` with:
  - `postgres:16-alpine` with healthcheck
  - `redis:7-alpine` with healthcheck
  - Volume mounts for persistence
- [ ] 🐳 Verify `docker compose -f docker/docker-compose.dev.yml up -d` starts cleanly
- [ ] 📋 Create `.env.example` with all required environment variables (see SSOT)
- [ ] 📋 Create `.env` (local, gitignored) from `.env.example`

### 0.4 — Configuration Layer
- [ ] 🔴 Write test: `settings` object loads all env vars correctly with defaults
- [ ] 🟢 Implement `app/core/config.py` using `pydantic-settings` `BaseSettings`
  - Fields: `DATABASE_URL`, `SYNC_DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `MAX_DELIVERY_ATTEMPTS`, `PORT`
  - Validators: ensure `DATABASE_URL` starts with `postgresql+asyncpg`
- [ ] 🔵 Add type annotations, docstrings

### 0.5 — Test Infrastructure Bootstrap
- [ ] 📋 Create `tests/conftest.py` with:
  - Async test database engine (uses `TEST_DATABASE_URL`)
  - `db_session` fixture (rolls back each test in transaction)
  - `async_client` fixture wrapping `httpx.AsyncClient` against the FastAPI app
- [ ] 📋 Create `pytest.ini` / `pyproject.toml` pytest section:
  - `asyncio_mode = auto`
  - `testpaths = tests`
  - Coverage config pointing to `app/`
- [ ] 🔴 Write a smoke test: `GET /health` returns 200 (will fail — route not yet built)
- [ ] 🟢 Add `/health` stub to `app/main.py` returning `{"status": "ok"}`

### ✅ Phase 0 Checkpoint
> `pytest` runs (smoke test passes), `ruff check .` passes, `mypy .` passes, dev infra containers start healthy, `/health` returns 200 via `curl`.

---

## Phase 1 — Database Layer (Models + Migrations)

> **Goal:** All three database tables defined as SQLAlchemy models, Alembic migrations applied, async session factory tested.

### 1.1 — SQLAlchemy Models
- [ ] 🔴 Write unit tests for model instantiation and relationships:
  - `Subscriber` can be created with required fields
  - `Event` stores `payload` as JSONB
  - `DeliveryLog` foreign keys resolve correctly (subscriber → delivery_log, event → delivery_log)
  - `DeliveryLog.status` defaults to `"pending"`
- [ ] 🟢 Implement `app/db/models.py`:
  - `Base = DeclarativeBase()`
  - `Subscriber` model (UUID PK, name, url, secret, event_types `ARRAY(Text)`, enabled, created_at)
  - `Event` model (UUID PK, event_type, payload `JSONB`, received_at)
  - `DeliveryLog` model (UUID PK, event_id FK, subscriber_id FK, attempt_number, status, response_status, response_body, duration_ms, attempted_at, next_retry_at)
  - Use `sqlalchemy.dialects.postgresql.UUID` and `JSONB`
- [ ] 🔵 Add `__repr__` methods, column comments, index on `delivery_log(event_id)` and `delivery_log(subscriber_id)`

### 1.2 — Async Session Factory
- [ ] 🔴 Write test: `get_db()` dependency yields an `AsyncSession`, session closes after request
- [ ] 🟢 Implement `app/db/session.py`:
  - `async_engine` via `create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)`
  - `AsyncSessionLocal` via `async_sessionmaker`
  - `get_db()` async generator (FastAPI dependency)
  - `SyncSession` context manager (for Celery tasks, uses `psycopg2` URL)
- [ ] 🔵 Add connection pool config (pool_size=10, max_overflow=20)

### 1.3 — Alembic Setup & Initial Migration
- [ ] 📋 Run `alembic init alembic/` and configure `alembic/env.py`:
  - Import `Base.metadata` from `app.db.models`
  - Configure async engine for online migrations
  - Set `target_metadata = Base.metadata`
- [ ] 📋 Generate initial migration: `alembic revision --autogenerate -m "initial_schema"`
- [ ] 📋 Review generated migration file — ensure `gen_random_uuid()`, `TIMESTAMPTZ`, `TEXT[]`, `JSONB` are correct
- [ ] 🔴 Write test: running Alembic `upgrade head` on test DB creates all three tables with correct columns
- [ ] 🟢 Run migration against dev DB: `alembic upgrade head`
- [ ] 🔵 Add `alembic upgrade head` to app startup event in `main.py` (dev only, guarded by env flag)

### 1.4 — Pydantic Schemas
- [ ] 🔴 Write tests for schema validation:
  - `SubscriberCreate` rejects missing `url` field
  - `SubscriberCreate` validates `url` is a valid HTTP/HTTPS URL
  - `DeliveryLogRead` serializes `attempted_at` as ISO string
- [ ] 🟢 Implement `app/db/schemas.py`:
  - `SubscriberCreate`, `SubscriberUpdate`, `SubscriberRead`
  - `EventCreate`, `EventRead`
  - `DeliveryLogRead`, `DeliveryLogSummary`
  - All `Read` schemas use `model_config = ConfigDict(from_attributes=True)`
- [ ] 🔵 Add field-level validators (`url` must be http/https, `event_types` must be non-empty strings if provided)

### ✅ Phase 1 Checkpoint
> All model tests pass, migration applies cleanly, `alembic current` shows `head`, schema validation tests pass.

---

## Phase 2 — Authentication

> **Goal:** JWT-based auth with token issuance endpoint; all protected routes reject requests without a valid token.

### 2.1 — JWT Core
- [ ] 🔴 Write unit tests for `security.py`:
  - `create_access_token(data)` returns a decodable JWT
  - `decode_token(token)` returns claims for valid token
  - `decode_token(expired_token)` raises `HTTPException 401`
  - `decode_token("garbage")` raises `HTTPException 401`
- [ ] 🟢 Implement `app/core/security.py`:
  - `create_access_token(data: dict, expires_delta: timedelta | None)` using `python-jose`
  - `decode_token(token: str)` with expiry check
  - Algorithm: HS256, secret from `settings.JWT_SECRET`
- [ ] 🔵 Parameterize token expiry via `settings.ACCESS_TOKEN_EXPIRE_MINUTES` (default 60)

### 2.2 — Auth Route & Dependency
- [ ] 🔴 Write integration tests for `POST /auth/token`:
  - Returns `access_token` and `token_type: bearer` for any request (service-to-service model — no user DB)
  - Returns proper Pydantic-shaped response
- [ ] 🔴 Write integration tests for `verify_jwt` dependency:
  - Request with valid `Authorization: Bearer <token>` → passes
  - Request with no header → `401`
  - Request with malformed header → `401`
  - Request with expired token → `401`
- [ ] 🟢 Implement `app/api/routes/auth.py` — `POST /auth/token` issues a JWT
- [ ] 🟢 Implement `verify_jwt` dependency in `app/api/deps.py`
- [ ] 🔵 Register `auth` router in `main.py` under `/auth` prefix

### ✅ Phase 2 Checkpoint
> All auth unit + integration tests pass, `POST /auth/token` returns a token, protected route returns 401 without it.

---

## Phase 3 — Subscriber Management API

> **Goal:** Full CRUD for subscribers with input validation, service layer separation, and comprehensive test coverage.

### 3.1 — Subscriber Service Layer
- [ ] 🔴 Write unit tests (mock DB session) for `subscriber_service.py`:
  - `create_subscriber(db, data)` persists and returns a `Subscriber`
  - `get_subscriber(db, id)` returns `None` for unknown UUID
  - `list_subscribers(db)` returns all enabled + disabled subscribers
  - `update_subscriber(db, id, data)` mutates only provided fields
  - `delete_subscriber(db, id)` sets `enabled=False` (soft delete) or hard deletes
- [ ] 🟢 Implement `app/services/subscriber_service.py` using async SQLAlchemy queries
- [ ] 🔵 Add pagination support (`limit`, `offset` params) to `list_subscribers`

### 3.2 — Subscriber Routes
- [ ] 🔴 Write integration tests for all subscriber endpoints (use `async_client` fixture, seed DB with factory):
  - `POST /subscribers` → 201, returns subscriber with generated UUID
  - `POST /subscribers` with duplicate URL → 409 (or allow duplicates per design — decide and document)
  - `GET /subscribers` → 200, returns list
  - `GET /subscribers` without JWT → 401
  - `PUT /subscribers/:id` → 200 with updated fields
  - `PUT /subscribers/:id` unknown ID → 404
  - `DELETE /subscribers/:id` → 204
  - `DELETE /subscribers/:id` unknown ID → 404
- [ ] 🟢 Implement `app/api/routes/subscribers.py` with all five routes
- [ ] 🔵 Register router in `main.py` under `/subscribers` prefix
- [ ] 🔵 Add `factory_boy` factory: `SubscriberFactory` for test data generation

### ✅ Phase 3 Checkpoint
> All 8 subscriber endpoint tests pass, 404/401/409 cases handled correctly, mypy clean.

---

## Phase 4 — Event Ingestion API

> **Goal:** `POST /events` persists an event, fans out to Celery (mocked in API-layer tests), and returns `202 Accepted` immediately.

### 4.1 — Event Service Layer
- [ ] 🔴 Write unit tests for `delivery_service.py`:
  - `create_event(db, data)` saves event and returns it with a UUID
  - `get_event_with_deliveries(db, event_id)` returns event + all delivery log rows
- [ ] 🟢 Implement `app/services/delivery_service.py` — async queries for events + delivery logs
- [ ] 🔵 Add `EventFactory` factory-boy factory

### 4.2 — Event Routes
- [ ] 🔴 Write integration tests for event endpoints (mock `fan_out_event.delay`):
  - `POST /events` with valid payload → 202, returns `{event_id, status: "queued"}`
  - `POST /events` without JWT → 401
  - `POST /events` with missing `event_type` → 422
  - `POST /events` with non-dict `payload` → 422
  - `GET /events/:id` → 200 with event + delivery status summary
  - `GET /events/:unknown_id` → 404
- [ ] 🟢 Implement `app/api/routes/events.py` — ingest + fan-out trigger + event detail
- [ ] 🟢 Register router in `main.py` under `/events` prefix
- [ ] 🔵 Ensure `fan_out_event.delay()` is called with the correct arguments (use `unittest.mock.patch`)

### 4.3 — Delivery Status Routes
- [ ] 🔴 Write tests for delivery log endpoints:
  - `GET /deliveries/:id` → 200 returns full delivery log row
  - `GET /deliveries/:id` unknown → 404
  - `GET /deliveries/:id/retry` → 202 for `dead` status delivery, 400 for non-dead
- [ ] 🟢 Implement `app/api/routes/deliveries.py`
- [ ] 🔵 `retry` endpoint should re-enqueue `deliver_webhook` task directly (mock Celery in test)

### ✅ Phase 4 Checkpoint
> All event + delivery route tests pass. `fan_out_event.delay` is verified to be called with correct args. 422 validation handled automatically by FastAPI.

---

## Phase 5 — Celery Worker: Fan-out & Delivery Tasks

> **Goal:** Fully working async delivery pipeline with retry logic, HMAC signing, and backoff schedule. Tested with mocked HTTP and real DB fixtures.

### 5.1 — Celery App Configuration
- [ ] 🔴 Write test: `celery_app` is importable and configured with correct broker/backend URLs
- [ ] 🟢 Implement `app/tasks/celery_app.py` per SSOT spec:
  - `task_serializer="json"`, `result_expires=3600`
  - `worker_prefetch_multiplier=1`, `task_acks_late=True`, `task_reject_on_worker_lost=True`
- [ ] 🔵 Add `beat_schedule` stub for future scheduled tasks

### 5.2 — Fan-out Task
- [ ] 🔴 Write unit tests for `fan_out_event` (mock DB, mock `deliver_webhook.apply_async`):
  - Given 3 matching subscribers → 3 `DeliveryLog` rows created + 3 `deliver_webhook.apply_async` calls
  - Subscriber with non-matching `event_types` → excluded from fan-out
  - Subscriber with `event_types=[]` (wildcard) → included in all events
  - Disabled subscriber (`enabled=False`) → excluded
- [ ] 🟢 Implement `app/tasks/fanout.py`:
  - Filter by `enabled=True`
  - Match `event_types` array: empty array = wildcard, else `event_type` must be in array
  - Create `DeliveryLog` row per subscriber with `status="pending"`
  - Fire `deliver_webhook.apply_async(args=[log_id, sub_id, payload], countdown=0)`
- [ ] 🔵 Wrap entire fan-out in a single DB transaction; commit only after all tasks are enqueued

### 5.3 — Delivery Task (Core)
- [ ] 🔴 Write unit tests for `deliver_webhook` (use `respx` to mock `httpx`):
  - Subscriber returns `200` → `DeliveryLog.status = "success"`, `response_status = 200`, `duration_ms` populated
  - Subscriber returns `500` → `DeliveryLog.status = "failed"`, task retried with first backoff (30s)
  - Subscriber returns `500` on final attempt → `DeliveryLog.status = "dead"`
  - Subscriber times out (`httpx.TimeoutException`) → treated as failure, triggers retry
  - `attempted_at` is set on each attempt
  - `next_retry_at` is set correctly on failure (based on backoff schedule)
- [ ] 🟢 Implement `app/tasks/delivery.py` per SSOT spec:
  - Set `status="delivering"` at start of each attempt
  - `BACKOFF_SCHEDULE = [30, 300, 1800, 7200, 28800]`
  - Catch all exceptions; on `MaxRetriesExceededError` → set `status="dead"`
  - Use `httpx.Client(timeout=10.0)` (sync client in Celery task)
- [ ] 🔵 Extract `_mark_delivering`, `_mark_success`, `_mark_failed`, `_mark_dead` as private helpers

### 5.4 — HMAC Signing
- [ ] 🔴 Write unit tests for HMAC header generation:
  - Subscriber with `secret="mysecret"` → request has `X-Webhook-Signature: sha256=<hex>`
  - Subscriber with no secret → `X-Webhook-Signature` header absent
  - Signature matches `hmac.new(secret.encode(), body, sha256).hexdigest()`
- [ ] 🟢 Implement HMAC signing inside `deliver_webhook` (already outlined in SSOT)
- [ ] 🔵 Extract `sign_payload(secret: str, body: bytes) -> str` as a pure function in `app/core/security.py`

### 5.5 — Retry Backoff Verification
- [ ] 🔴 Write parametrized test: for each attempt index 0–4, assert `countdown` matches `BACKOFF_SCHEDULE[attempt]`
- [ ] 🔴 Write test: after 5 retries (6 total attempts), task does NOT retry — sets `status="dead"`
- [ ] 🟢 Confirm implementation satisfies all parametrized cases
- [ ] 🔵 Assert `MAX_DELIVERY_ATTEMPTS` env variable is respected if set

### ✅ Phase 5 Checkpoint
> All fan-out + delivery task tests pass. HMAC signing tests pass. Backoff schedule parametrized tests pass (30s → 5m → 30m → 2h → 8h). Dead-letter logic verified.

---

## Phase 6 — Middleware & Structured Logging

> **Goal:** Every request gets a unique `X-Request-ID`, all logs are structured JSON with request context, errors are handled uniformly.

### 6.1 — Request ID Middleware
- [ ] 🔴 Write test: every response includes `X-Request-ID` header (UUID format)
- [ ] 🔴 Write test: if client sends `X-Request-ID`, the same value is echoed back
- [ ] 🟢 Implement `app/api/middleware.py` — Starlette `BaseHTTPMiddleware` subclass
- [ ] 🔵 Attach `request_id` to a context var for use in log records

### 6.2 — Structured JSON Logging
- [ ] 📋 Implement `app/core/logging.py`:
  - Configure `structlog` or stdlib `logging` with JSON formatter
  - Every log record includes: `timestamp`, `level`, `logger`, `request_id`, `message`
  - Log all incoming requests (method, path, status_code, duration_ms) in middleware
- [ ] 🔴 Write test: log output is valid JSON when logger is called
- [ ] 🟢 Wire structured logging into `main.py` startup

### 6.3 — Global Error Handling
- [ ] 🔴 Write tests for error scenarios:
  - Unhandled `Exception` → 500 with JSON body `{"detail": "Internal server error"}` (no stack trace leaked)
  - `HTTPException` → standard FastAPI JSON error
  - Validation error → 422 with FastAPI's default schema
- [ ] 🟢 Add `@app.exception_handler(Exception)` in `main.py`
- [ ] 🔵 Log all 5xx errors with full traceback (to log only, not response body)

### ✅ Phase 6 Checkpoint
> All middleware tests pass, every response has `X-Request-ID`, logs are valid JSON, 500s return safe error bodies.

---

## Phase 7 — Observability (Prometheus Metrics)

> **Goal:** All custom metrics are registered, incremented correctly per delivery outcome, and `/metrics` is reachable without auth.

### 7.1 — Prometheus Metrics Module
- [ ] 🔴 Write unit tests for metrics:
  - `deliveries_success` counter increments on `status="success"`
  - `deliveries_failed` counter increments on each failed attempt
  - `deliveries_dead` counter increments when status hits `"dead"`
  - `delivery_duration` histogram records a value > 0 on each attempt
- [ ] 🟢 Implement `app/observability/metrics.py` per SSOT spec:
  - `deliveries_success_total`, `deliveries_failed_total`, `deliveries_dead_total` (Counters, labeled by `subscriber_id`)
  - `webhook_delivery_duration_seconds` (Histogram, labeled by `subscriber_id`, custom buckets)
  - Wire `Instrumentator().instrument(app).expose(app, endpoint="/metrics")`
- [ ] 🔵 Import and call metric helpers from `deliver_webhook` task
- [ ] 🔵 Ensure `/metrics` endpoint is excluded from JWT auth

### 7.2 — Health Endpoint
- [ ] 🔴 Write tests for `GET /health`:
  - Returns `200` with `{"status": "ok", "db": "ok", "redis": "ok"}` when all deps healthy
  - Returns `503` with failing component identified if DB or Redis unreachable (mock the connections)
- [ ] 🟢 Implement `GET /health` in `main.py` (or dedicated `routes/health.py`):
  - Ping DB with `SELECT 1`
  - Ping Redis with `PING`
  - Aggregate status; return 503 if any check fails
- [ ] 🔵 Add `worker` health check stub (check Celery inspect ping)

### ✅ Phase 7 Checkpoint
> `GET /metrics` returns Prometheus text format, counters verified in tests, `GET /health` returns 200 with all deps healthy, 503 when unhealthy (mocked).

---

## Phase 8 — Containerization & Production Docker Setup

> **Goal:** API and worker run as separate Docker images; `docker compose up` brings up the full stack end-to-end.

### 8.1 — API Dockerfile
- [ ] 🐳 Create `docker/Dockerfile` (multi-stage):
  - Stage 1 `builder`: install deps into `/install`
  - Stage 2 `runtime`: copy `/install`, copy `app/`, expose `8000`
  - Use `python:3.12-slim` base
  - `CMD uvicorn app.main:app --host 0.0.0.0 --port 8000`
- [ ] 🔴 Write test: `docker build -f docker/Dockerfile .` exits 0 (CI shell test)
- [ ] 🔵 Add `.dockerignore` excluding `.venv`, `__pycache__`, `.env`, `tests/`

### 8.2 — Worker Dockerfile
- [ ] 🐳 Create `docker/Dockerfile.worker` (separate image for Celery worker):
  - Same base as API but different `CMD`:
    `celery -A app.tasks.celery_app worker --loglevel=info --concurrency=8`
  - Install only prod requirements (no test deps)
- [ ] 🔴 Write test: `docker build -f docker/Dockerfile.worker .` exits 0

### 8.3 — Production Docker Compose
- [ ] 🐳 Create `docker/docker-compose.yml` per SSOT spec:
  - `api` service (port 8000, depends on db + redis healthy)
  - `worker` service (2 replicas, no exposed ports)
  - `db` (postgres:16-alpine, volume `pg_data`, healthcheck)
  - `redis` (redis:7-alpine, healthcheck)
  - `prometheus` (prom/prometheus, `prometheus.yml` volume mount, port 9090)
- [ ] 🐳 Create `docker/prometheus.yml` scrape config pointing at `api:8000/metrics`
- [ ] 🐳 Add `POSTGRES_INITDB_ARGS: "--auth=scram-sha-256"` for prod security
- [ ] 🔵 Use Docker secrets or env file for `JWT_SECRET` (not hardcoded)

### 8.4 — Smoke Test: Full Stack
- [ ] 🐳 Script `scripts/smoke_test.sh`:
  - `docker compose up -d`
  - Wait for `GET /health` → 200 (poll with retry)
  - `POST /auth/token` → capture token
  - `POST /subscribers` with token → 201
  - `POST /events` with token → 202
  - Poll `GET /events/:id` until delivery `status = "success"` (max 30s)
  - `GET /metrics` → verify `webhook_deliveries_success_total` > 0
  - `docker compose down -v`
- [ ] 🔴 Wire smoke test into CI as a separate job

### ✅ Phase 8 Checkpoint
> `docker compose up` starts all services healthy, smoke test script exits 0, full delivery pipeline completes successfully.

---

## Phase 9 — Integration & End-to-End Tests

> **Goal:** High-confidence test suite covering cross-component flows with a real (test) database — no mocks for the happy path.

### 9.1 — Integration Test Infrastructure
- [ ] 📋 Create `tests/integration/conftest.py`:
  - Spin up real PostgreSQL (use `pytest-docker` or assume dev containers running)
  - Run `alembic upgrade head` against test DB before session
  - Provide `real_async_client` fixture (no mocked services)
  - Provide `celery_worker` fixture using `celery.contrib.pytest` eager mode (`CELERY_TASK_ALWAYS_EAGER=True`)
- [ ] 📋 Separate unit tests (`tests/unit/`) from integration tests (`tests/integration/`) in pytest marks (`@pytest.mark.integration`)

### 9.2 — Fan-out Integration Tests
- [ ] 🔴 Write integration test:
  - Create 3 subscribers (2 matching event type, 1 wildcard, 1 wrong type)
  - Ingest event via `POST /events`
  - Assert 3 `DeliveryLog` rows created (not 4 — wrong type excluded)
  - Assert `deliver_webhook` was called for each (eager mode)
- [ ] 🟢 Fix any issues exposed by real DB interactions

### 9.3 — Retry Integration Tests
- [ ] 🔴 Write integration test for retry flow (mock only the HTTP call):
  - Subscriber endpoint returns 500 twice, then 200
  - Assert final `DeliveryLog.status = "success"` after 3rd attempt
  - Assert `attempt_number = 3` in the final log
- [ ] 🔴 Write integration test for dead-letter:
  - Subscriber always returns 500
  - Assert final `DeliveryLog.status = "dead"` after max attempts

### 9.4 — Manual Retry Integration Test
- [ ] 🔴 Write test for `GET /deliveries/:id/retry`:
  - Create a `dead` delivery log
  - Call retry endpoint → 202
  - Assert `deliver_webhook` task is re-queued (mock apply_async or use eager mode)

### 9.5 — Coverage Gate
- [ ] 📋 Configure pytest-cov with `--cov-fail-under=85`
- [ ] 📋 Add coverage badge to README (via CI artifact)
- [ ] 🔵 Identify and fill any gaps below 85% threshold

### ✅ Phase 9 Checkpoint
> Integration tests pass with real DB, coverage ≥ 85%, all retry/dead-letter/fan-out flows verified end-to-end.

---

## Phase 10 — Documentation & Developer Experience

> **Goal:** The project is fully documented such that a new developer can understand, run, and contribute to the system without prior context.

### 10.1 — README.md (Root)
- [ ] 📝 Write `README.md` with:
  - **What this is** — one-paragraph description
  - **Architecture diagram** (reproduce ASCII art from SSOT, or link Mermaid version)
  - **Quick Start** — `git clone` → `docker compose up` → `curl` examples, all commands copy-pasteable
  - **Environment Variables** table with descriptions, defaults, and whether required
  - **API Reference** table (all endpoints, method, auth, description)
  - **Running Tests** section: unit tests, integration tests, coverage report commands
  - **Project Structure** tree with one-line description per file/folder

### 10.2 — Inline Code Documentation
- [ ] 📝 Ensure every public function/class has a Google-style docstring
  - Parameters, return type, raises, and a one-line summary
- [ ] 📝 Add module-level docstrings to every `app/**/*.py` file
- [ ] 📝 Annotate all Celery tasks with docstrings explaining: trigger, inputs, side effects, retry behavior
- [ ] 📝 Add comments to `alembic/env.py` explaining async migration setup
- [ ] 🔴 Write a `mypy` check as part of CI that fails if type annotations are missing from public APIs

### 10.3 — Architecture Decision Records (ADRs)
- [ ] 📝 Create `docs/adr/` directory
- [ ] 📝 Write ADR-001: Choice of Celery over pure async (asyncio task queue)
  - Context, Decision, Consequences
- [ ] 📝 Write ADR-002: Sync SQLAlchemy for Celery tasks vs async for FastAPI
  - Why two drivers (`asyncpg` + `psycopg2`)
- [ ] 📝 Write ADR-003: JWT as service-to-service auth (no user accounts)
- [ ] 📝 Write ADR-004: Exponential backoff schedule selection rationale
- [ ] 📝 Write ADR-005: Soft-delete vs hard-delete for subscribers

### 10.4 — API Documentation
- [ ] 📝 Enrich all FastAPI route decorators with `summary`, `description`, `response_description`
- [ ] 📝 Add `openapi_extra` tags for grouping in Swagger UI
- [ ] 📝 Create `app/api/openapi_examples.py` with example request/response bodies for all endpoints
- [ ] 📝 Verify `/docs` (Swagger UI) and `/redoc` are accessible and render correctly

### 10.5 — Operational Runbook
- [ ] 📝 Create `docs/runbook.md`:
  - **Scaling workers**: how to increase Celery concurrency / replicas
  - **Monitoring dashboards**: key Prometheus metrics to watch, alert thresholds
  - **Dead letter management**: how to query dead deliveries, force retry via API
  - **Database maintenance**: index health, `delivery_log` table growth estimates, archival strategy
  - **Redis memory management**: eviction policy recommendation for broker queue
  - **Rotating JWT secret**: zero-downtime rotation procedure

### 10.6 — CONTRIBUTING Guide
- [ ] 📝 Create `CONTRIBUTING.md`:
  - Development setup instructions (step-by-step, OS-agnostic)
  - Pre-commit hook setup
  - How to run the full test suite
  - Branching strategy (e.g., `feature/*`, `fix/*`)
  - PR checklist (tests pass, coverage maintained, mypy clean, docs updated)

### 10.7 — Changelog
- [ ] 📝 Create `CHANGELOG.md` using Keep a Changelog format
  - `[Unreleased]` section populated with all features from Phase 0–9
  - Version `0.1.0` tagged on completion of all phases

### ✅ Phase 10 Checkpoint
> README renders correctly on GitHub, all public functions have docstrings, `/docs` Swagger UI shows all endpoints with examples, 5 ADRs written, runbook covers all operational scenarios.

---

## Phase 11 — CI/CD Pipeline

> **Goal:** Every push to `main` runs the full test suite and builds Docker images. PRs are blocked until all checks pass.

### 11.1 — GitHub Actions: Test Workflow
- [ ] 📋 Create `.github/workflows/test.yml`:
  - Trigger: push to `main`, pull_request to `main`
  - Services: `postgres:16-alpine`, `redis:7-alpine` (GitHub Actions service containers)
  - Steps:
    1. Checkout
    2. Set up Python 3.12
    3. Cache pip dependencies
    4. Install `requirements.txt` + `requirements-dev.txt`
    5. Run `alembic upgrade head`
    6. `ruff check .`
    7. `mypy .`
    8. `pytest tests/unit/ --cov=app --cov-report=xml`
    9. Upload coverage to Codecov

### 11.2 — GitHub Actions: Integration Test Workflow
- [ ] 📋 Create `.github/workflows/integration.yml`:
  - Trigger: push to `main` only (not PRs — heavier)
  - Run `pytest tests/integration/ -m integration`
  - Run `scripts/smoke_test.sh` using Docker Compose

### 11.3 — GitHub Actions: Docker Build Workflow
- [ ] 📋 Create `.github/workflows/docker.yml`:
  - Build `docker/Dockerfile` and `docker/Dockerfile.worker`
  - Tag with `git sha` and `latest`
  - Push to GitHub Container Registry (GHCR) on merge to `main`

### ✅ Phase 11 Checkpoint
> All three GitHub Actions workflows pass, PR checks are enforced, Docker images are published to GHCR on merge.

---

## Summary: Phase Dependencies & Sequencing

```
Phase 0 (Foundation)
    │
    ├─► Phase 1 (Database)
    │       │
    │       ├─► Phase 2 (Auth)
    │       │       │
    │       │       └─► Phase 3 (Subscribers)
    │       │                   │
    │       │                   └─► Phase 4 (Events)
    │       │                               │
    │       └─► Phase 5 (Celery Worker) ───┘
    │                   │
    │                   └─► Phase 6 (Middleware)
    │                               │
    │                               └─► Phase 7 (Observability)
    │                                           │
    └───────────────────────────────────────────┴─► Phase 8 (Docker)
                                                            │
                                                    Phase 9 (Integration Tests)
                                                            │
                                                    Phase 10 (Documentation)
                                                            │
                                                    Phase 11 (CI/CD)
```

---

## Effort Estimates

| Phase | Mini-phases | Est. Time | TDD Cycles |
|-------|-------------|-----------|------------|
| 0 — Foundation | 5 | 2–3 hrs | 1 |
| 1 — Database | 4 | 3–4 hrs | 5 |
| 2 — Auth | 2 | 2 hrs | 4 |
| 3 — Subscribers | 2 | 3 hrs | 8 |
| 4 — Event Ingest | 3 | 3 hrs | 6 |
| 5 — Celery Worker | 5 | 5–6 hrs | 10 |
| 6 — Middleware | 3 | 2 hrs | 3 |
| 7 — Observability | 2 | 2 hrs | 4 |
| 8 — Docker | 4 | 3 hrs | 2 |
| 9 — Integration Tests | 5 | 4 hrs | 8 |
| 10 — Documentation | 7 | 4–5 hrs | 1 |
| 11 — CI/CD | 3 | 2 hrs | 0 |
| **Total** | **45** | **~35–37 hrs** | **52** |

---

## TDD Discipline Contract

> These rules apply to every mini-phase without exception:

1. **Red first.** No production code is written before a failing test exists for it.
2. **Smallest possible green.** Make the test pass with the minimum code change.
3. **Refactor under green.** Only clean up code when all tests are passing.
4. **One test at a time.** Do not write a batch of tests before implementing anything.
5. **Test names describe behavior.** `test_deliver_webhook_marks_dead_after_max_retries` not `test_delivery_3`.
6. **No test skips.** `pytest.mark.skip` is forbidden unless accompanied by a linked GitHub Issue.
7. **Coverage is a floor, not a ceiling.** 85% is the minimum; aim for meaningful coverage over line count.
8. **Mock at boundaries.** Mock HTTP calls (`respx`), external services, and time (`freezegun`). Never mock the unit under test.
