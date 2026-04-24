#!/bin/bash
# deploy.sh — Pull latest code and restart services
# Usage: ./deploy.sh [IMAGE_TAG]

set -euo pipefail

IMAGE_TAG=${1:-latest}
COMPOSE_FILE="docker-compose.yml"
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

echo "[deploy] Starting deployment — tag: $IMAGE_TAG"
echo "[deploy] App directory: $APP_DIR"

cd "$APP_DIR"

# Pull latest code
echo "[deploy] Pulling latest code from git..."
git pull origin main

# Export image tag for compose
export IMAGE_TAG="$IMAGE_TAG"

# Run database migrations as one-off step before starting app
echo "[deploy] Running database migrations..."
docker compose -f "$COMPOSE_FILE" run --rm api \
  python -m app.database.setup_no_embed || true

# Pull new images and restart services
echo "[deploy] Pulling images and restarting services..."
docker compose -f "$COMPOSE_FILE" pull api
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

# Wait for health check
echo "[deploy] Waiting for API to become healthy..."
RETRIES=30
until docker compose -f "$COMPOSE_FILE" exec api curl -sf http://localhost:5000/health > /dev/null 2>&1; do
  RETRIES=$((RETRIES - 1))
  if [ $RETRIES -eq 0 ]; then
    echo "[deploy] ERROR: API did not become healthy in time"
    docker compose -f "$COMPOSE_FILE" logs api --tail=50
    exit 1
  fi
  echo "[deploy] Waiting... ($RETRIES retries left)"
  sleep 3
done

echo "[deploy] Deployment complete!"
