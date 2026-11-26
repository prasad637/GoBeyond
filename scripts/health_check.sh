#!/usr/bin/env bash
# ==============================================================================
# GO BEYOND — Stack Health, Migration, Worker & Monitoring Check
# ==============================================================================
set -euo pipefail

WAIT_SECONDS="${1:-30}"
BASE_URL="${BASE_URL:-http://localhost}"
PROM_URL="${PROM_URL:-http://localhost:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3001}"

EXPECTED_CONTAINERS=(
  gobeyond-postgres
  gobeyond-redis
  gobeyond-backend
  gobeyond-worker
  gobeyond-frontend
  gobeyond-nginx
  gobeyond-prometheus
  gobeyond-grafana
)

echo "[HEALTH] Waiting for 8 Docker containers (timeout ${WAIT_SECONDS}s)..."
deadline=$(( $(date +%s) + WAIT_SECONDS ))
while true; do
  all_ok=true
  for c in "${EXPECTED_CONTAINERS[@]}"; do
    status=$(docker inspect -f '{{.State.Running}}:{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$c" 2>/dev/null || echo "missing")
    if [[ "$status" != "true:healthy" ]]; then
      all_ok=false
      break
    fi
  done
  if $all_ok; then
    break
  fi
  if (( $(date +%s) >= deadline )); then
    echo "[FAIL] Not all 8 containers became healthy within ${WAIT_SECONDS}s." >&2
    docker compose ps >&2 || true
    exit 1
  fi
  sleep 3
done
echo "[PASS] All 8 containers running and healthy."

check_code() {
  local url="$1"
  local expected="$2"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url")
  if [[ "$code" != "$expected" ]]; then
    echo "[FAIL] GET $url expected HTTP $expected, got $code" >&2
    return 1
  fi
}

check_code "${BASE_URL}/nginx-health" 200
check_code "${BASE_URL}/health" 200
check_code "${BASE_URL}/health/ready" 200
check_code "${BASE_URL}/" 200
check_code "${BASE_URL}/api/v1/discovery/home?city_slug=hyderabad" 200
check_code "${BASE_URL}/metrics" 403
check_code "${BASE_URL}/health/detailed" 403

if ! docker exec gobeyond-backend alembic current | grep -q "(head)"; then
  echo "[FAIL] Alembic migration is not at head." >&2
  exit 1
fi

hb=$(docker exec gobeyond-redis redis-cli EXISTS gobeyond:worker:heartbeat | tr -d '[:space:]')
if [[ "$hb" != "1" ]]; then
  echo "[FAIL] Worker heartbeat key gobeyond:worker:heartbeat missing in Redis." >&2
  exit 1
fi

check_code "${PROM_URL}/api/v1/targets" 200
check_code "${PROM_URL}/api/v1/rules" 200
check_code "${GRAFANA_URL}/api/health" 200

echo "[PASS] NGINX routes, /metrics 403 block, DB/Redis readiness, Alembic (head), ARQ worker heartbeat, Prometheus, and Grafana verified."

