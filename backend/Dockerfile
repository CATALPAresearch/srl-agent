FROM python:3.12-slim

WORKDIR /api

# Install system deps needed by psycopg2 (libpq) and curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cached layer)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Append institution CA cert so requests to internal services work
RUN cat ./certs/chat-impact-fernuni-hagen-de.pem \
    >> /usr/local/lib/python3.12/site-packages/certifi/cacert.pem

# docker-compose overrides this CMD with setup_no_embed + gunicorn
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:5000", "--timeout", "300", "--workers", "2"]
