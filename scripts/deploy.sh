#!/usr/bin/env bash
# ==============================================================================
# GO BEYOND — Safe Local / Staging Deployment Script
# ==============================================================================
set -euo pipefail

MODE="local"
ENV_FILE=".env"
WAIT_SECONDS=120
NO_BUILD=false
PROD_OVERLAY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) MODE="$2"; shift 2 ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --timeout) WAIT_SECONDS="$2"; shift 2 ;;
    --no-build) NO_BUILD=true; shift ;;
    --prod) PROD_OVERLAY=true; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== GO BEYOND Deployment Automation (mode=${MODE}, prod_overlay=${PROD_OVERLAY}) ==="

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[ERROR] Environment file '$ENV_FILE' not found." >&2
  exit 1
fi

PYTHON_BIN="python3"
if [[ -x "backend/.venv/bin/python" ]]; then
  PYTHON_BIN="backend/.venv/bin/python"
fi

"$PYTHON_BIN" scripts/validate_env.py --env-file "$ENV_FILE" --mode "$MODE"

docker info >/dev/null

COMPOSE_ARGS=(-f docker-compose.yml)
if $PROD_OVERLAY; then
  COMPOSE_ARGS+=(-f docker-compose.prod.yml)
fi

docker compose "${COMPOSE_ARGS[@]}" config --quiet

if ! $NO_BUILD; then
  echo "[DEPLOY] Building backend & frontend images..."
  docker compose "${COMPOSE_ARGS[@]}" build
fi

echo "[DEPLOY] Starting / updating containers cleanly (preserving all volumes)..."
docker compose "${COMPOSE_ARGS[@]}" up -d

"${SCRIPT_DIR}/health_check.sh" "$WAIT_SECONDS"

echo "=== Deployment Status ==="
docker compose "${COMPOSE_ARGS[@]}" ps

