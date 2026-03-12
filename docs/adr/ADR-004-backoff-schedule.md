# ADR-004: Exponential Backoff Schedule Selection

**Date:** 2025-01-15  
**Status:** Accepted  
**Deciders:** Backend team

---

## Context

Webhook delivery failures are common in practice — subscriber endpoints go down for maintenance, experience transient load spikes, or return 5xx errors during deploys. The retry strategy must balance:

- **Promptness** — retrying quickly increases the chance of catching short outages.
- **Back-pressure** — retrying too aggressively amplifies load on a struggling endpoint.
- **Coverage window** — retrying for a meaningful total window catches longer maintenance periods.
- **Resource cost** — more retries = more Celery tasks, more DB writes, more Redis entries.

The system configuration variable `MAX_DELIVERY_ATTEMPTS` defaults to 6.

---

## Decision

We use a **fixed exponential backoff schedule** defined in `app/tasks/delivery.py`:

```python
BACKOFF_SCHEDULE = [30, 300, 1800, 7200, 28800]  # seconds
# 30s → 5 min → 30 min → 2 h → 8 h
```

The first attempt is immediate (no delay). Each retry uses the next countdown from the schedule. With `max_retries = len(BACKOFF_SCHEDULE) = 5`, there are **6 total attempts** (1 initial + 5 retries).

**Total coverage window:** 30s + 5m + 30m + 2h + 8h = **~10.5 hours**

---

## Rationale

| Attempt | Delay | Cumulative wait | Rationale |
|---|---|---|---|
| 1 (initial) | 0s | 0s | Immediate — most transient failures resolve instantly |
| 2 | 30s | 30s | Catch quick recoveries (pod restart, brief overload) |
| 3 | 5 min | ~5.5 min | Catch short deploy windows |
| 4 | 30 min | ~36 min | Catch extended deploys or partial outages |
| 5 | 2 h | ~2.6 h | Catch multi-hour maintenance windows |
| 6 | 8 h | ~10.5 h | Final attempt before dead-lettering |

The schedule was derived from common industry patterns (GitHub, Stripe, Shopify webhooks all use similar windows). A 10.5-hour window covers the majority of real-world subscriber downtime scenarios without holding delivery state indefinitely.

---

## Consequences

- After 6 failed attempts the `DeliveryLog.status` is set to `dead`. Operators can inspect dead deliveries and trigger a manual retry via `GET /deliveries/{id}/retry`.
- The `next_retry_at` column in `delivery_log` is written on each failure so operators and monitoring dashboards can see when the next attempt is scheduled.
- The schedule is a constant — it can be made configurable per-subscriber in a future phase if different SLAs are needed.
- Jitter is **not** applied. For a service with a small number of subscribers this is acceptable; at high fan-out scale, random jitter (±10–20%) should be added to avoid thundering-herd retries.
