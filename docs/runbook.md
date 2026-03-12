# Webhook Delivery Service — Operational Runbook

> This document is for operators and on-call engineers. It covers day-to-day operational tasks, alert responses, and maintenance procedures.

---

## Table of Contents

1. [Scaling Workers](#1-scaling-workers)
2. [Monitoring Dashboards](#2-monitoring-dashboards)
3. [Dead Letter Management](#3-dead-letter-management)
4. [Database Maintenance](#4-database-maintenance)
5. [Redis Memory Management](#5-redis-memory-management)
6. [Rotating the JWT Secret](#6-rotating-the-jwt-secret)

---

## 1. Scaling Workers

### Celery concurrency

Each Celery worker process runs a pool of threads/subprocesses. The default concurrency equals the number of CPU cores.

**Increase concurrency on a single worker:**

```bash
celery -A app.tasks.celery_app worker --concurrency=16 --loglevel=info
```

**Docker Compose — scale worker replicas:**

```bash
docker compose -f docker/docker-compose.yml up -d --scale worker=4
```

Each replica picks tasks from the same Redis queue. Horizontal scaling is safe because:
- Each task processes a single `delivery_log` row by primary key.
- `task_acks_late=True` ensures a task is only removed from the queue after it finishes; if a worker dies mid-task, the task is automatically re-queued.

### Recommended scaling triggers

| Metric | Threshold | Action |
|---|---|---|
| Redis queue depth (`celery` key length) | > 1 000 tasks | Add worker replicas |
| `webhook_delivery_duration_seconds` p95 | > 5s | Investigate subscriber latency or increase workers |
| Worker CPU | > 80% sustained | Increase concurrency or add replicas |

### Graceful shutdown

Send `SIGTERM` to a worker to allow in-flight tasks to complete before exiting:

```bash
docker compose -f docker/docker-compose.yml stop worker
```

---

## 2. Monitoring Dashboards

### Prometheus metrics

The API server exposes metrics at `GET /metrics`. The Celery worker does not expose an HTTP endpoint; metrics are written directly from task code via `prometheus_client`.

| Metric | Type | Labels | Description |
|---|---|---|---|
| `deliveries_success_total` | Counter | `subscriber_id` | Successful webhook POSTs (2xx response) |
| `deliveries_failed_total` | Counter | `subscriber_id` | Failed attempts that will be retried |
| `deliveries_dead_total` | Counter | `subscriber_id` | Deliveries permanently dead (max retries exhausted) |
| `webhook_delivery_duration_seconds` | Histogram | `subscriber_id` | End-to-end HTTP POST duration in seconds |
| `http_requests_total` | Counter | `method`, `handler`, `status` | FastAPI request counts (from `prometheus-fastapi-instrumentator`) |
| `http_request_duration_seconds` | Histogram | `method`, `handler` | FastAPI request latency |

### Key alert thresholds

| Alert | Expression | Severity |
|---|---|---|
| Dead deliveries spiking | `rate(deliveries_dead_total[5m]) > 0.1` | Warning |
| High failure rate | `rate(deliveries_failed_total[5m]) / rate(deliveries_success_total[5m]) > 0.5` | Warning |
| Slow subscriber responses | `histogram_quantile(0.95, webhook_delivery_duration_seconds) > 8` | Warning |
| API 5xx rate | `rate(http_requests_total{status=~"5.."}[5m]) > 0.05` | Critical |
| Health check degraded | `up{job="webhook-delivery"} == 0` | Critical |

### Checking health

```bash
curl http://localhost:8000/health
# {"status":"ok","db":"ok","redis":"ok"}
# Returns 503 if DB or Redis are unreachable.
```

---

## 3. Dead Letter Management

### What is a dead delivery?

A `DeliveryLog` row with `status = 'dead'` has exhausted all retry attempts (default: 6). The subscriber's endpoint consistently returned non-2xx responses or was unreachable.

### Find dead deliveries

```sql
-- All dead deliveries in the last 24 hours
SELECT dl.id, dl.event_id, dl.subscriber_id, dl.attempted_at, dl.response_status
FROM delivery_log dl
WHERE dl.status = 'dead'
  AND dl.attempted_at > NOW() - INTERVAL '24 hours'
ORDER BY dl.attempted_at DESC;

-- Dead deliveries per subscriber
SELECT s.name, s.url, COUNT(*) AS dead_count
FROM delivery_log dl
JOIN subscribers s ON s.id = dl.subscriber_id
WHERE dl.status = 'dead'
GROUP BY s.name, s.url
ORDER BY dead_count DESC;
```

### Manually retry a dead delivery

Use the API:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token | jq -r .access_token)

curl -s -X GET http://localhost:8000/deliveries/<log_id>/retry \
  -H "Authorization: Bearer $TOKEN"
# {"status":"requeued"}
```

This re-enqueues the delivery immediately. The delivery worker will attempt it once more; the `attempt_number` resets to 1.

### Bulk retry all dead deliveries for a subscriber

```bash
# Get all dead log IDs for a specific subscriber
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token | jq -r .access_token)

psql "$DATABASE_URL" -t -c \
  "SELECT id FROM delivery_log WHERE status='dead' AND subscriber_id='<sub_id>'" \
  | xargs -I{} curl -s -X GET http://localhost:8000/deliveries/{}/retry \
    -H "Authorization: Bearer $TOKEN"
```

### When NOT to retry

- If the subscriber endpoint is permanently decommissioned — delete the subscriber instead.
- If the event payload was malformed on your side — fix the payload and re-send the event rather than retrying the dead delivery.

---

## 4. Database Maintenance

### Index health

The following indexes are critical for performance:

```sql
-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename IN ('delivery_log', 'events', 'subscribers')
ORDER BY idx_scan ASC;
```

Indexes with zero or very low `idx_scan` may be candidates for removal. Indexes with high tuple reads confirm they are being used.

### `delivery_log` table growth

Each event fan-out creates one row per subscriber. Estimate growth:

```
rows/day ≈ events/day × avg_subscribers × avg_attempts_per_delivery
```

Example: 10 000 events/day × 5 subscribers × 1.2 attempts = ~60 000 rows/day ≈ 21M rows/year.

**Check current table size:**

```sql
SELECT
  pg_size_pretty(pg_total_relation_size('delivery_log')) AS total_size,
  COUNT(*) AS row_count
FROM delivery_log;
```

### Archival strategy

For long-running deployments, periodically archive old `delivery_log` rows to a cold storage table or export to object storage:

```sql
-- Archive delivery logs older than 90 days to a cold table
INSERT INTO delivery_log_archive
SELECT * FROM delivery_log
WHERE attempted_at < NOW() - INTERVAL '90 days';

DELETE FROM delivery_log
WHERE attempted_at < NOW() - INTERVAL '90 days';
```

Run `VACUUM ANALYZE delivery_log;` after large deletes to reclaim space and update statistics.

### Connection pool sizing

The async engine uses SQLAlchemy's default pool size. For high-concurrency deployments, tune via `DATABASE_URL` query parameters or by modifying `create_async_engine` kwargs in `app/db/session.py`:

```python
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)
```

---

## 5. Redis Memory Management

### Recommended eviction policy

Redis is used as both the Celery **broker** (task queue) and **result backend**. For broker usage, data loss must be avoided. Set:

```
maxmemory-policy noeviction
```

This causes Redis to return errors on new writes when memory is full, rather than silently evicting task data. This forces operators to address memory growth rather than losing tasks.

**To set on a running Redis instance:**

```bash
redis-cli CONFIG SET maxmemory-policy noeviction
```

Persist this in `redis.conf` for production deployments.

### Result backend expiry

Celery task results expire after 1 hour (`result_expires=3600` in `app/tasks/celery_app.py`). Monitor result backend memory with:

```bash
redis-cli INFO memory | grep used_memory_human
redis-cli DBSIZE  # total key count
```

### Queue depth monitoring

```bash
# Check pending task count in the default queue
redis-cli LLEN celery

# List all queues
redis-cli KEYS "celery*"
```

Alert if `LLEN celery` exceeds your worker throughput capacity (see scaling section above).

---

## 6. Rotating the JWT Secret

The `JWT_SECRET` signs all access tokens. If it is compromised or as part of scheduled rotation, follow this procedure to rotate it with zero downtime.

### Step 1 — Generate a new secret

```bash
python -c "import secrets; print(secrets.token_hex(32))"
# Store in your secrets manager / vault
```

### Step 2 — Dual-key transition period (optional, zero-downtime)

If you need existing tokens to remain valid during the rollover window, temporarily accept both old and new secrets by running two API instances with different `JWT_SECRET` values behind a load balancer. After the old tokens expire (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 60 min), all traffic will use the new secret.

For most deployments a brief token invalidation (step 3) is acceptable.

### Step 3 — Update the secret

Update `JWT_SECRET` in your secrets manager / `.env` and redeploy:

```bash
# Update .env (or your orchestration secret store)
JWT_SECRET=<new-secret>

# Redeploy the API
docker compose -f docker/docker-compose.yml up -d --force-recreate api
```

**Effect:** all existing tokens are immediately invalidated. Callers must re-issue tokens via `POST /auth/token`.

### Step 4 — Verify

```bash
# Old token should now return 401
curl -s http://localhost:8000/auth/me \
  -H "Authorization: Bearer <old-token>"
# {"detail":"could not validate credentials"}

# New token should work
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token | jq -r .access_token)
curl -s http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"
# {"sub":"service","exp":...}
```
