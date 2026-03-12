# ADR-005: Hard-Delete for Subscribers

**Date:** 2025-01-15  
**Status:** Accepted  
**Deciders:** Backend team

---

## Context

When a subscriber is deleted via `DELETE /subscribers/{id}`, we must decide whether to:

1. **Hard-delete** — remove the row from the database immediately. Foreign-key constraints on `delivery_log` are handled by `ON DELETE CASCADE`.
2. **Soft-delete** — add a `deleted_at TIMESTAMPTZ` column; set it on "deletion"; exclude soft-deleted rows from all queries; retain the row and all associated delivery logs indefinitely.

---

## Decision

We use **hard-delete** for subscribers.

---

## Reasons

| Criterion | Hard-delete | Soft-delete |
|---|---|---|
| Implementation complexity | Low — `db.delete(sub)` | High — every query needs `WHERE deleted_at IS NULL` |
| Data retention | Delivery logs cascade-deleted | Delivery logs retained; historical record preserved |
| GDPR / data minimisation | Simpler — data is truly gone | Requires explicit purge process for true deletion |
| Accidental deletion risk | Cannot undo without a DB backup | Can undo by nullifying `deleted_at` |
| Query performance | No filter overhead | Requires index on `deleted_at` |

For a service where subscribers are registered by internal engineers (not end users), the risk of accidental deletion is low and acceptable. The simplicity of hard-delete outweighs the auditability benefit of soft-delete at this stage.

---

## Consequences

- `DELETE /subscribers/{id}` permanently removes the subscriber row.
- All associated `delivery_log` rows are cascade-deleted (enforced by the `ForeignKey("subscribers.id")` constraint in SQLAlchemy and the `ON DELETE CASCADE` in the Alembic migration).
- There is no "recycle bin" or undelete API.
- If audit trail of past deliveries is required in the future, the recommended approach is to introduce soft-delete at that point by adding a `deleted_at` column via a new Alembic migration and updating all relevant queries.
- Operators should treat deletion as irreversible. Backups of `delivery_log` should be maintained per the retention policy in `docs/runbook.md`.
