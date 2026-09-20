#!/bin/bash
# healthcheck.sh — Check health of all services
# Usage: ./healthcheck.sh
# Exit code 0 = all healthy, 1 = one or more unhealthy

set -uo pipefail

APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$APP_DIR"

FAILED=0

check() {
  local NAME=$1
  local CMD=$2
  if eval "$CMD" > /dev/null 2>&1; then
    echo "[OK]   $NAME"
  else
    echo "[FAIL] $NAME"
    FAILED=1
  fi
}

echo "=== SRL-Agent Healthcheck ==="

# API
check "Flask API /health" \
  "curl -sf http://localhost:5000/health"

# PostgreSQL
check "PostgreSQL" \
  "docker compose exec postgresql pg_isready -d srl_chat -U chat"

# Nginx
check "Nginx" \
  "curl -sf http://localhost:80/ -o /dev/null"

# Grafana
check "Grafana" \
  "curl -sf http://localhost:3000/api/health"

# Loki
check "Loki" \
  "curl -sf http://localhost:3100/ready"

echo "==========================="
if [ $FAILED -eq 0 ]; then
  echo "All services healthy."
else
  echo "One or more services are unhealthy!"
  exit 1
fi
