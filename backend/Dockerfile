# Build context: repository root (see docker-compose.yml)

# --- Stage 1: build the Vue frontend bundle (webpack → ../backend/static/lti) ---
FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- Stage 2: API ---
FROM python:3.12.5-slim

WORKDIR /api

# Install system deps needed by psycopg2 (libpq) and curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry

# Install Python dependencies first (cached layer)
COPY backend/pyproject.toml backend/poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-root

# Copy application code (logs/ is excluded via .dockerignore and mounted at runtime)
COPY backend/ .
RUN mkdir -p logs

# Frontend: built bundle + the static files served from /frontend (index.html, core stubs)
COPY --from=frontend /build/backend/static/lti/app-lazy.js ./static/lti/app-lazy.js
COPY frontend/index.html /frontend/index.html
COPY frontend/core /frontend/core

# Append institution CA cert so requests to internal services work
RUN cat ./certs/chat-impact-fernuni-hagen-de.pem \
    >> /usr/local/lib/python3.12/site-packages/certifi/cacert.pem

# docker-compose overrides this CMD with setup_no_embed + gunicorn
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:5000", "--timeout", "300", "--workers", "2"]
