# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Phase 10: full project documentation
  - `README.md` with architecture diagram, quick-start guide, env vars table, API reference, test instructions, and project structure tree
  - `docs/runbook.md` covering scaling, monitoring, dead-letter management, DB maintenance, Redis memory, and JWT rotation
  - `CONTRIBUTING.md` with dev setup, pre-commit, TDD discipline, branching strategy, and PR checklist
  - `CHANGELOG.md` (this file)
  - `docs/adr/` directory with five Architecture Decision Records:
    - ADR-001: Celery over a pure-asyncio task queue
    - ADR-002: Dual SQLAlchemy drivers (asyncpg + psycopg2)
    - ADR-003: JWT as service-to-service authentication
    - ADR-004: Exponential backoff schedule selection
    - ADR-005: Hard-delete for subscribers
  - `app/api/openapi_examples.py` — reusable OpenAPI request/response example dicts
  - Enriched all FastAPI route decorators with `summary`, `description`, `response_description`, and `responses` (404/400/401 examples)
  - Google-style docstrings on all public functions; enriched Celery task docstrings with trigger, side-effects, and retry behaviour

---

## [0.1.0] — 2026-03-12

### Added

#### Phase 0 — Project Foundation
- Python 3.12 project skeleton with `pyproject.toml`, `ruff`, `mypy` strict mode, and pre-commit hooks
- `docker/docker-compose.dev.yml` with PostgreSQL 16 and Redis 7 dev containers
- `app/core/config.py` — `pydantic-settings` `Settings` class loading all env vars with validation
- `app/core/logging.py` — `structlog` structured JSON logging
- `GET /health` readiness probe checking DB and Redis connectivity

#### Phase 1 — Database Layer
- SQLAlchemy 2.0 ORM models: `Subscriber`, `Event`, `DeliveryLog` (`app/db/models.py`)
- Pydantic v2 request/response schemas (`app/db/schemas.py`)
- Async session factory (`asyncpg`) and sync session factory (`psycopg2`) in `app/db/session.py`
- Alembic async migration environment (`alembic/env.py`) with initial migration creating all three tables

#### Phase 2 — Authentication
- `app/core/security.py` — JWT creation (`create_access_token`), decoding (`decode_token`), and HMAC-SHA256 signing (`sign_payload`)
- `POST /auth/token` — issues service-to-service JWTs (no user database)
- `GET /auth/me` — returns decoded JWT claims
- `app/api/deps.py` — FastAPI `verify_jwt` dependency (OAuth2PasswordBearer scheme)

#### Phase 3 — Subscriber CRUD
- `app/services/subscriber_service.py` — async CRUD (create, read, list, update, delete)
- Full REST endpoints: `POST /subscribers`, `GET /subscribers`, `GET /subscribers/{id}`, `PUT /subscribers/{id}`, `DELETE /subscribers/{id}`
- Hard-delete semantics with cascade on `delivery_log` foreign keys

#### Phase 4 — Event Ingest
- `POST /events/` — persists event, commits, fires `fan_out_event.delay()`, returns 202
- `GET /events/{id}` — returns event with all delivery log summaries
- `app/services/delivery_service.py` — `create_event`, `get_event_with_deliveries`, `get_delivery_log`

#### Phase 5 — Celery Worker
- `app/tasks/celery_app.py` — Celery instance with Redis broker/backend; `task_acks_late=True`, `task_reject_on_worker_lost=True`, `worker_prefetch_multiplier=1`
- `app/tasks/fanout.py` — `fan_out_event` task: queries matching + wildcard subscribers, creates `DeliveryLog` rows, dispatches `deliver_webhook` tasks
- `app/tasks/delivery.py` — `deliver_webhook` task and `_run_delivery` helper:
  - HMAC-SHA256 request signing via `X-Webhook-Signature` header
  - Exponential backoff schedule: 30s → 5m → 30m → 2h → 8h
  - State machine: pending → delivering → success / failed → dead
  - Prometheus metric recording on success, failure, and dead-letter

#### Phase 6 — Middleware
- `app/api/middleware.py` — `RequestIDMiddleware`: injects `X-Request-ID` header, binds to structlog context vars, emits structured access log per request

#### Phase 7 — Observability
- `app/observability/metrics.py` — Prometheus counters (`deliveries_success_total`, `deliveries_failed_total`, `deliveries_dead_total`) and histogram (`webhook_delivery_duration_seconds`)
- `prometheus-fastapi-instrumentator` exposing `GET /metrics`
- `docker/prometheus.yml` Prometheus scrape configuration

#### Phase 8 — Docker / Containerisation
- `docker/Dockerfile` — multi-stage API server image
- `docker/Dockerfile.worker` — Celery worker image
- `docker/docker-compose.yml` — full production-like stack (API, worker, Postgres, Redis, Prometheus)
- `scripts/smoke_test.sh` — end-to-end smoke test script
- `tests/unit/test_docker_build.py` — Docker build validation tests (gated by `RUN_DOCKER_TESTS=1`)

#### Phase 9 — Integration & End-to-End Tests
- `tests/integration/test_fanout_integration.py` — 5 tests: fan-out matching, wildcard, disabled-subscriber exclusion, correct subscriber ID dispatch, pending-status seeding
- `tests/integration/test_delivery_flow.py` — 7 tests: success/200, duration_ms recording, attempt_number, failed/500, next_retry_at, dead after max retries, dead on ConnectionError
- `tests/integration/conftest.py` — `sync_test_session_factory` fixture (psycopg2 → test DB) and deadlock-safe `clean_tables` fixture
- `integration` pytest marker added to `pyproject.toml`

### Fixed
- `app/tasks/delivery.py`: `DetachedInstanceError` — `sub.url` and `sub.secret` are now extracted inside the first `SyncSession` block before the session closes
- `app/tasks/delivery.py`: `response_status` was not persisted for failed deliveries because `raise Exception(...)` was inside the second `with SyncSession()` block causing rollback before commit — moved `raise` outside the block

### Changed
- `tests/integration/conftest.py`: `clean_tables` fixture changed from `pytest.fixture` to `pytest_asyncio.fixture` to fix a PostgreSQL lock deadlock that caused integration tests to hang indefinitely

---

[Unreleased]: https://github.com/<your-org>/webhook-delivery/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/<your-org>/webhook-delivery/releases/tag/v0.1.0
