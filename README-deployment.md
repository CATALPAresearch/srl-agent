# SRL Chat – Deployment Guide

This document covers local development setup, Docker Compose deployment, and the GitLab CI/CD pipeline.

Servername: catalpa-p-interviews-vm.fernuni-hagen.de
IP: 132.176.108.172
OS: RedHat 9.7 (Plow)
Mailkontakt: niels.seidel@fernuni-hagen.de

Hinterlegte Benutzer\*innen + SSH-Keys sind:

- seidel (Root-Rechte)

ssh srlagent
/opt/srl-chat/

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Local Development (no Docker)](#local-development-no-docker)
4. [Docker Compose](#docker-compose)
5. [CI/CD Pipeline](#cicd-pipeline)
6. [Server Setup (first time)](#server-setup-first-time)
7. [Monitoring (Grafana / Loki)](#monitoring-grafana--loki)
8. [Healthcheck](#healthcheck)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Tool                    | Version       | Purpose                |
| ----------------------- | ------------- | ---------------------- |
| Python                  | 3.12          | Backend                |
| Node.js                 | 18            | Frontend build         |
| Docker + Docker Compose | 24+           | Container runtime      |
| PostgreSQL              | 16 + pgvector | Database               |
| Ollama                  | any           | LLM inference endpoint |

---

## Environment Configuration

Copy `env.example` to `.env` and fill in the values:

```bash
cp env.example .env
```

Key variables:

| Variable                            | Description                                  | Default                   |
| ----------------------------------- | -------------------------------------------- | ------------------------- |
| `BASE_URL`                          | Ollama API base URL                          | `http://localhost:11434/` |
| `MODEL`                             | Ollama model name                            | `phi3:latest`             |
| `OLLAMA_NUM_PREDICT`                | Max tokens per LLM response                  | `256`                     |
| `OLLAMA_NUM_CTX`                    | Context window size                          | `2048`                    |
| `PG_HOST`                           | PostgreSQL host                              | `localhost`               |
| `PG_USER` / `PG_PASSWORD` / `PG_DB` | Database credentials                         | —                         |
| `SECRET_KEY`                        | Flask session secret                         | —                         |
| `ADMIN_PASSWORD`                    | Password for admin overlay in the UI         | `admin`                   |
| `DISABLE_LLM`                       | Skip LLM calls (UI dev mode)                 | `false`                   |
| `INTERVIEW_PROTOCOL`                | Interview config file name (without `.json`) | `interview_default`       |

For Docker Compose, change `PG_HOST=postgresql` (the service name).

---

## Local Development (no Docker)

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root (or `backend/`), then:

```bash
# Create database tables and seed reference data
python -m app.database.setup_no_embed

# Run the development server
flask --app app run --port 5000 --debug
```

The API is available at `http://localhost:5000`.  
The frontend is served at `http://localhost:5000/` (Flask reads `frontend/index.html`).

### 2. Frontend (watch mode)

```bash
cd frontend
npm install
npm run watch        # rebuilds to backend/static/lti/ on change
```

Webpack outputs to `backend/static/lti/app-lazy.js`. A page refresh picks up changes immediately.

### 3. LLM backend

Start Ollama and pull a model:

```bash
ollama serve
ollama pull phi3:latest
```

Set `BASE_URL=http://localhost:11434/` in `.env`.  
Set `DISABLE_LLM=true` to skip LLM calls entirely during UI development.

---

## Docker Compose

All services are defined in `docker-compose.yml`:

| Service      | Image                    | Role                         |
| ------------ | ------------------------ | ---------------------------- |
| `api`        | built from `backend/`    | Flask application + gunicorn |
| `nginx`      | `nginx:alpine`           | Reverse proxy (port 80/443)  |
| `postgresql` | `pgvector/pgvector:pg16` | Database                     |
| `loki`       | `grafana/loki:2.9.0`     | Log aggregation              |
| `promtail`   | `grafana/promtail:2.9.0` | Log shipper                  |
| `grafana`    | `grafana/grafana:10.2.0` | Log dashboard (port 3000)    |

### First run

```bash
# 1. Build the image and start all services
docker compose up -d --build

# 2. Watch logs
docker compose logs -f api
```

The app is available at `http://localhost`.

### Stopping / restarting

```bash
docker compose down          # stop, keep volumes
docker compose down -v       # stop and delete all data (destructive!)
docker compose restart api   # restart only the API
```

### Build the frontend first

The Docker image includes the pre-built frontend bundle (`backend/static/lti/app-lazy.js`). Before building the image, build the frontend:

```bash
cd frontend && npm ci && NODE_OPTIONS=--openssl-legacy-provider npm run build
cd ..
docker compose build api
```

In CI this is done automatically by the `vue-build` job before `build-push-api`.

### Config volume mounts

The `api` service mounts two host directories:

```
./backend/config  →  /api/config   (read-only: prompts, interview protocol, survey)
./frontend        →  /frontend     (read-only: index.html, served by Flask)
```

Editing `backend/config/prompts.json` on the host takes effect after restarting the api service:

```bash
docker compose restart api
```

---

## CI/CD Pipeline

The GitLab CI pipeline (`.gitlab-ci.yml`) has four stages:

```
lint → test → build → deploy
```

### Stage overview

| Job                 | Stage  | Runs when                            |
| ------------------- | ------ | ------------------------------------ |
| `vue-lint`          | lint   | frontend files changed               |
| `python-lint`       | lint   | backend files changed                |
| `python-test`       | test   | backend/tests changed, or on `main`  |
| `vue-build`         | test   | frontend files changed, or on `main` |
| `build-push-api`    | build  | `main` branch or tag                 |
| `deploy-production` | deploy | `main` branch, **manual trigger**    |

### Required CI/CD variables

No secrets required — the pipeline runs lint and tests only. Deployment is done manually on the server.

### How a deploy works

1. Push to `main` triggers the pipeline.
2. `vue-build` compiles the frontend bundle to `backend/static/lti/`.
3. `build-push-api` builds a Docker image (including the fresh bundle) and pushes it to the GitLab container registry with the commit SHA as tag.
4. `deploy-production` is triggered **manually** in the GitLab pipeline UI.
5. The deploy job SSHes into the server, runs `git pull`, and calls `infrastructure/scripts/deploy.sh <IMAGE_TAG>`.
6. `deploy.sh` pulls the new image, runs database migrations, and restarts all services.

---

## Server Setup (first time)

### 1. Install Docker

Create a public key pair on the server and add the public key to your git instance (e.g. GitLab or GitHub).

```bash
ssh-keygen -t ed25519 -C "your name"
cat ~/.ssh/id_ed25519.pub
```

**Red Hat / Rocky Linux / AlmaLinux (RHEL-based):**

```bash
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # allow non-root docker use; re-login after
newgrp docker
```

**Ubuntu / Debian:**

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

> **RHEL note:** Red Hat ships Podman by default, but this stack uses Docker CE for full Compose v2 compatibility. Do not use `podman-compose` — it lacks feature parity.

### 2. Create deploy user and directory

```bash
sudo useradd -m deploy
sudo mkdir -p /opt/srl-chat
sudo chown deploy:deploy /opt/srl-chat
```

### 3. Clone the repository

```bash
sudo -u deploy git clone <repo-url> /opt/srl-chat
```

### 4. Configure environment

```bash
cd /opt/srl-chat
sudo -u deploy cp env.example .env
sudo -u deploy nano .env   # fill in production values
```

Minimum values to set for production:

```bash
BASE_URL=http://<ollama-host>:11434/
MODEL=phi3:latest
PG_HOST=postgresql
PG_USER=postgres
PG_PASSWORD=<strong-password>
PG_DB=srl_chat
SECRET_KEY=<random-64-char-string>
ADMIN_PASSWORD=<strong-password>
GRAFANA_PASSWORD=<strong-password>
REGISTRY=registry.example.com
```

### 5. Give the server git access to the repository

The server needs to pull code from GitLab. Generate a key pair **on the server** and add the public key as a GitLab Deploy Key (read-only).

```bash
# On the server, as the deploy user
sudo -u deploy ssh-keygen -t ed25519 -C "srl-chat-server-deploy" -f /home/deploy/.ssh/id_ed25519
sudo cat /home/deploy/.ssh/id_ed25519.pub
```

Copy the output and add it in GitLab:  
**Settings → Repository → Deploy keys → Add new key** (read-only is sufficient).

### 6. Open firewall port (RHEL)

```bash
sudo firewall-cmd --permanent --add-port=${APP_PORT:-8081}/tcp
sudo firewall-cmd --reload
```

### 7. Login to the container registry

The deploy script pulls the Docker image built by CI. The server needs registry access once:

```bash
docker login registry.gitlab.com
```

### 8. Start services

```bash
cd /opt/srl-chat
docker compose up -d
docker compose logs -f api   # watch startup
```

After this, deployments are triggered via the GitLab pipeline.

---

## Monitoring (Grafana / Loki)

Grafana is available at `http://<server>:3000` (default credentials: `admin` / value of `GRAFANA_PASSWORD`).

> **Security:** Port 3000 should not be publicly accessible. Restrict it via firewall to trusted IPs only, or proxy it through nginx with HTTP basic auth.

Promtail ships log files from `backend/logs/*.log` to Loki. To query logs in Grafana:

1. Add a Loki data source: URL = `http://loki:3100`
2. Use the Explore view with query: `{job="srl-chat-api"}`

To make Flask write structured logs to `backend/logs/`, ensure the app's logging is configured to write to that directory (it is volume-mounted into the container at `/api/logs`).

> **Note:** Grafana runs on port 3000 directly. If you want it behind nginx with authentication, add a `location /grafana/` proxy block to `infrastructure/nginx/conf.d/srl-chat.conf`.

---

## Healthcheck

Run the healthcheck script on the server to verify all services:

```bash
bash /opt/srl-chat/infrastructure/scripts/healthcheck.sh
```

Expected output:

```
=== SRL-Chat Healthcheck ===
[OK]   Flask API /health
[OK]   PostgreSQL
[OK]   Nginx
[OK]   Grafana
[OK]   Loki
===========================
All services healthy.
```

The Flask API also exposes a `/health` endpoint directly:

```bash
curl http://localhost:5000/health
# {"service": "srl-chat", "status": "ok"}
```

---

## Troubleshooting

**API container fails to start**

```bash
docker compose logs api --tail=100
```

Common causes: database not reachable yet (wait for healthy), missing `.env` variable, migration error.

**Frontend not loading**

The frontend JS bundle is served at `/static/lti/app-lazy.js`. Check:

```bash
docker compose exec api ls /api/static/lti/
# should list app-lazy.js
```

If missing, the image was built without a frontend build step. Rebuild:

```bash
cd frontend && npm ci && NODE_OPTIONS=--openssl-legacy-provider npm run build && cd ..
docker compose build api && docker compose up -d api
```

**Admin login not working**

The admin password is injected into `index.html` as `window.SRL_ADMIN_PASSWORD` by Flask at request time. Verify:

```bash
curl -s http://localhost:5000/ | grep SRL_ADMIN_PASSWORD
```

If the line is missing, check that `ADMIN_PASSWORD` is set in `.env` and the api container was restarted after the change.

**Database connection refused**

Check postgresql is healthy before the api starts:

```bash
docker compose ps postgresql
docker compose logs postgresql --tail=30
```

**Prompt changes not taking effect**

Prompts are cached in memory (`lru_cache`). After editing `backend/config/prompts.json`:

```bash
docker compose restart api
```

**Out of disk space (logs / Loki)**

```bash
docker system prune -f                  # remove unused images/containers
docker compose logs --tail=0 api        # stop tailing if stuck
```

Loki data is stored in the `srl-chat-loki` named volume. To trim it, stop loki and delete the volume (loses log history):

```bash
docker compose stop loki promtail
docker volume rm srl-chat-loki
docker compose up -d loki promtail
```
