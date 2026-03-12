# ADR-003: JWT as Service-to-Service Authentication

**Date:** 2025-01-15  
**Status:** Accepted  
**Deciders:** Backend team

---

## Context

The webhook delivery API is an internal service consumed by other backend services, not end users. Authentication options considered:

1. **API keys** — a static shared secret stored in the database, looked up on every request.
2. **JWT (JSON Web Tokens)** — stateless bearer tokens, self-contained, expirable, signed with a shared secret.
3. **mTLS** — mutual TLS certificate authentication at the infrastructure layer.
4. **OAuth 2.0 client credentials** — a full OAuth server issues tokens; calling services use client_id + client_secret.

---

## Decision

We use **JWT with HS256** (`python-jose`) as a stateless bearer token scheme for service-to-service authentication.

`POST /auth/token` returns a signed JWT to any caller. The token is passed as a `Bearer` token in `Authorization` headers on all subsequent requests.

---

## Reasons

- **No user database** — this service does not have users. API keys would require a secrets table and a lookup query per request; JWTs avoid both.
- **Stateless verification** — `decode_token()` validates the token with only the `JWT_SECRET` from environment config; no database round-trip.
- **Standard tooling** — `python-jose` is well-maintained and integrates cleanly with FastAPI's `OAuth2PasswordBearer` security scheme.
- **Expiry built-in** — the `exp` claim limits the token lifetime (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 60 min) without maintaining a revocation list.
- **mTLS** was ruled out as it requires infrastructure-level certificate management which is out of scope for this phase.
- **OAuth 2.0** was ruled out as overkill for a single-service internal API.

---

## Consequences

- **No revocation** — tokens cannot be individually revoked before expiry. Rotation requires changing `JWT_SECRET`, which invalidates all existing tokens simultaneously. See `docs/runbook.md` for the zero-downtime rotation procedure.
- **Secret management** — `JWT_SECRET` must be treated as a high-value secret. Rotate it via the procedure in the runbook if compromised.
- The `POST /auth/token` endpoint currently issues tokens to any caller with no further checks. In a future phase, this could be gated behind an API-key or IP allowlist if the service is exposed beyond a trusted internal network.
- `GET /auth/me` allows callers to inspect their decoded claims, which is useful for debugging token issues.
