#!/usr/bin/env bash
# smoke_test.sh - end-to-end test that brings up the full stack and verifies
# the complete webhook delivery pipeline.
#
# usage:
#   scripts/smoke_test.sh
#
# optional env vars:
#   JWT_SECRET        - overrides the generated secret (default: random)
#   POSTGRES_PASSWORD - postgresql password (default: postgres)
#
# requires: docker, docker compose v2, python3, curl

set -euo pipefail

# navigate to repo root regardless of where the script is invoked from
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker/docker-compose.yml --project-name webhook-delivery"
BASE_URL="http://localhost:8000"
MAX_WAIT=60

# generate a random jwt secret if not provided
export JWT_SECRET="${JWT_SECRET:-$(python3 -c 'import secrets; print(secrets.token_hex(32))')}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"

# --------------------------------------------------------------------------
# cleanup on exit
# --------------------------------------------------------------------------
cleanup() {
    echo "cleaning up..."
    $COMPOSE --profile smoke down -v 2>/dev/null || true
}
trap cleanup EXIT

# --------------------------------------------------------------------------
# start the full stack (with the echo service via --profile smoke)
# --------------------------------------------------------------------------
echo "building and starting full stack..."
$COMPOSE --profile smoke up -d --build

# --------------------------------------------------------------------------
# wait for api to become healthy
# --------------------------------------------------------------------------
echo "waiting for api health endpoint..."
elapsed=0
until curl -sf "$BASE_URL/health" \
    | python3 -c "import sys, json; d=json.load(sys.stdin); sys.exit(0 if d.get('status')=='ok' else 1)" 2>/dev/null
do
    sleep 2
    elapsed=$((elapsed + 2))
    if [ "$elapsed" -ge "$MAX_WAIT" ]; then
        echo "api did not become healthy within ${MAX_WAIT}s"
        $COMPOSE logs api
        exit 1
    fi
done
echo "api healthy"

# --------------------------------------------------------------------------
# obtain jwt token (no credentials required - service-to-service auth)
# --------------------------------------------------------------------------
TOKEN=$(
    curl -sf -X POST "$BASE_URL/auth/token" \
    | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])"
)
echo "auth token obtained"

# --------------------------------------------------------------------------
# create a subscriber pointing to the echo service
# traefik/whoami returns 200 for any http method
# --------------------------------------------------------------------------
SUB_ID=$(
    curl -sf -X POST "$BASE_URL/subscribers" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"name":"smoke-test","url":"http://echo","event_types":["smoke.test"]}' \
    | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])"
)
echo "subscriber created: $SUB_ID"

# --------------------------------------------------------------------------
# ingest an event
# --------------------------------------------------------------------------
EVENT_ID=$(
    curl -sf -X POST "$BASE_URL/events" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"event_type":"smoke.test","payload":{"smoke":true}}' \
    | python3 -c "import sys, json; print(json.load(sys.stdin)['event_id'])"
)
echo "event ingested: $EVENT_ID"

# --------------------------------------------------------------------------
# poll for delivery success (max 30s)
# --------------------------------------------------------------------------
echo "polling for delivery success..."
elapsed=0
while true; do
    STATUS=$(
        curl -sf "$BASE_URL/events/$EVENT_ID" \
            -H "Authorization: Bearer $TOKEN" \
        | python3 -c "
import sys, json
d = json.load(sys.stdin)
logs = d.get('deliveries', [])
print(logs[0]['status'] if logs else 'pending')
" 2>/dev/null || echo "pending"
    )
    echo "  delivery status: $STATUS"
    if [ "$STATUS" = "success" ]; then
        break
    fi
    sleep 2
    elapsed=$((elapsed + 2))
    if [ "$elapsed" -ge 30 ]; then
        echo "delivery did not succeed within 30s"
        $COMPOSE logs worker
        exit 1
    fi
done
echo "delivery succeeded"

# --------------------------------------------------------------------------
# verify prometheus metric is present
# --------------------------------------------------------------------------
if curl -sf "$BASE_URL/metrics" | grep -q "deliveries_success_total"; then
    echo "metrics: deliveries_success_total verified"
else
    echo "ERROR: deliveries_success_total not found in /metrics output"
    exit 1
fi

echo ""
echo "smoke test passed"
