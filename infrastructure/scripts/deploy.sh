#!/bin/bash
# deploy.sh — Pull latest image and restart services
# Usage: IMAGE_TAG=<sha> bash infrastructure/scripts/deploy.sh [IMAGE_TAG]
# Called by GitLab CI after git pull is done by the CI job itself.

set -euo pipefail

IMAGE_TAG=${1:-latest}
COMPOSE_FILE="docker-compose.yml"
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

echo "[deploy] Starting deployment — tag: $IMAGE_TAG"
echo "[deploy] App directory: $APP_DIR"

cd "$APP_DIR"

if [ ! -f ".env" ]; then
  echo "[deploy] ERROR: .env file not found in $APP_DIR"
  echo "[deploy] Create it once on the server: cp env.example .env && nano .env"
  exit 1
fi

export IMAGE_TAG="$IMAGE_TAG"

# Pull new image first so migrations run with the new code
echo "[deploy] Pulling new API image..."
docker compose -f "$COMPOSE_FILE" pull api

# Run database migrations with the new image before starting the app
echo "[deploy] Running database migrations..."
docker compose -f "$COMPOSE_FILE" run --rm api \
  python -m app.database.setup_no_embed || true

# Start all services (recreates api with new image)
echo "[deploy] Starting services..."
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
