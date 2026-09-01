FROM python:3.12.5-slim

WORKDIR /api

# Install system deps needed by psycopg2 (libpq) and curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry

# Install Python dependencies first (cached layer)
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-root

# Copy application code and pre-built frontend
COPY . /api/

# Append institution CA cert so requests to internal services work
RUN cat ./certs/chat-impact-fernuni-hagen-de.pem \
    >> /usr/local/lib/python3.12/site-packages/certifi/cacert.pem

# docker-compose overrides this CMD with setup_no_embed + gunicorn
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:5000", "--timeout", "300", "--workers", "2"]
