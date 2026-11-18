# SRL Chat Technical Documentation

This document contains architecture and implementation details, environment configuration, deployment internals, API surface, data model, and testing guidance.

## 1. Architecture

High-level runtime architecture:

- Frontend: Vue 2 web client (built bundle served by backend)
- Backend: Flask application with interview state machine
- Database: PostgreSQL (+ pgvector if RAG embeddings are enabled)
- Optional services:
  - LTI launch flow for LMS integration
  - Discord bot
  - RAG embedding/seeding pipeline

Typical flow:

1. User starts conversation via /startConversation
2. Backend loads protocol/prompts and updates conversation state
3. User replies via /reply
4. Strategies are detected and persisted
5. Frequency ratings are collected
6. Interview summary is generated and stored
7. Survey responses are submitted and linked to user run

## 2. Repository Structure

```text
srl-agent/
├── backend/
│   ├── main.py
│   ├── pyproject.toml
│   ├── app/
│   │   ├── core.py
│   │   ├── steps.py
│   │   ├── llm.py
│   │   ├── rag.py
│   │   ├── models.py
│   │   ├── actions.py
│   │   ├── logging_utlis.py
│   │   ├── lti.py
│   │   ├── lti_client.py
│   │   ├── routes/
│   │   └── database/
│   ├── config/
│   │   ├── interview/
│   │   ├── prompts.json
│   │   ├── translations.json
│   │   ├── survey_srl-o.json
│   │   ├── survey_srl-o_de.json
│   │   ├── survey_srl-o_en.json
│   │   ├── learning_strategies.json
│   │   ├── learning_strategies_v1.json
│   │   └── strategy_code_map.json
│   └── static/lti/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── router/
│   │   └── store/
│   └── webpack.config.js
├── tests/
├── docs/
├── docker-compose.yml
├── develop.docker-compose.yml
└── env.example
```

## 3. Environment Configuration (.env)

The `.env` file lives in the **project root** (next to `docker-compose.yml`). `backend/.env` is also supported as a legacy fallback.

Key variables:

```ini
BASE_URL=http://localhost:11434/
API_KEY=
MODEL=phi3:latest

OLLAMA_NUM_PREDICT=256
OLLAMA_NUM_CTX=2048

# Alternative to PG_* — overrides all individual DB vars when set
DATABASE_URL=

PG_HOST=localhost
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=postgres
PG_DB=srl_chat

# long random value, e.g. python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=<random-hex>

# JSON file in config/interview/ (without .json extension)
INTERVIEW_PROTOCOL=interview_default

# Set to true to skip LLM calls (useful for UI development)
DISABLE_LLM=false

USE_RAG_STRATEGY=false
RAG_EMBEDDING_MODEL=nomic-embed-text

# Optional: HuggingFace embeddings (only for setup.py with embeddings)
EMBEDDING_URL=
EMBEDDING_MODEL=
EMBEDDING_TOKEN=

# Optional: Discord bot
BOT_TOKEN=
DISCORD_SERVER_ID=
API_URL=http://api:5000
```

LTI-specific values depend on your LMS setup (consumer key/secret on LMS side plus matching provider configuration).

## 4. Database Setup and Seeding

Prerequisites:

- PostgreSQL >= 16
- pgvector extension if embeddings/RAG are needed

Initialize DB:

```bash
createdb srl_chat
psql -d srl_chat -c "CREATE EXTENSION IF NOT EXISTS vector"
```

Seed options:

```bash
cd backend

# Without embeddings (faster local setup)
poetry run python -m app.database.setup_no_embed

# Full setup including embeddings
poetry run python -m app.database.setup

# Demo data only
poetry run python -m app.database.seed_demo
```

## 5. Deployment Modes

### Stand-alone

```bash
cd backend
poetry install
poetry run python -m app.database.setup_no_embed

cd ../frontend
npm install        # requires Node.js >= 22.15 (Vue 3 / webpack 5)
npm run build

cd ../backend
poetry run python main.py                  # http://127.0.0.1:5000, debugger off
FLASK_DEBUG=1 poetry run python main.py    # with debugger + auto reload (local only)
```

`main.py` listens on `127.0.0.1` only. Use `HOST=<ip>` to reach it from other devices, but never
together with `FLASK_DEBUG=1`: the Werkzeug debugger allows running code from the browser.

### LTI deployment

- Launch endpoint: /lti/launch (renders the UI directly after a verified launch)
- Configure the LMS external tool with launch URL, consumer key and shared secret, and set the same
  values as `LTI_CONSUMER_KEY` / `LTI_SHARED_SECRET` in `.env`. Every launch must carry a valid
  OAuth 1.0 HMAC-SHA1 signature; unsigned, tampered, expired or replayed launches are rejected (401).
- Ensure HTTPS in production LMS setups

For detailed Moodle-centric setup, see [README-LTI.md](README-LTI.md).

### Docker Compose

```bash
cp example.env .env

# Dev stack
docker compose -f develop.docker-compose.yml up postgres-dev api-dev

# Prod-like stack
docker compose build --no-cache
docker compose up -d
```

The API image is built with `network: host` (needed on the RedHat server, where firewalld
blocks pypi/npm from the default build network). Newer Docker Compose versions build via
`buildx bake` and then stop with *"additional privileges requested: pass --allow=network.host"*.
Use the classic builder, or grant the privilege explicitly:

```bash
COMPOSE_BAKE=false docker compose build --no-cache
# or
docker buildx bake -f docker-compose.yml --allow=network.host --no-cache api
docker compose up -d
```

## 6. API Endpoints

### Chat

| Method | Path               | Description                   |
| ------ | ------------------ | ----------------------------- |
| POST   | /startConversation | Start a new interview session |
| POST   | /reply             | Submit a user message         |
| POST   | /resetConversation | Reset current session         |
| GET    | /conversation      | Retrieve conversation history |

### Survey

| Method | Path                    | Description               |
| ------ | ----------------------- | ------------------------- |
| GET    | /survey/`<id>`          | Load survey definition    |
| POST   | /survey/`<id>`/submit   | Submit survey answers     |
| GET    | /survey/`<id>`/results  | Retrieve survey results   |
| GET    | /student/results        | Student interview results |
| GET    | /student/interview_runs | Student run list          |

### Interview protocols

Protocols are JSON files in `backend/config/interview/` (several may exist). The active one is
selected with `INTERVIEW_PROTOCOL` in `.env` (file name without `.json`). There is no editor
and no API to change them: protocols steer the LLM prompts, so they are edited in the
repository (reviewed and versioned by git) and deployed like code. In Docker the directory is
mounted read-only.

### Dashboard

| Method | Path               | Description                     |
| ------ | ------------------ | ------------------------------- |
| GET    | /dashboard/stats   | Aggregated interview statistics |
| GET    | /dashboard/courses | Course list                     |

### User

| Method | Path            | Description           |
| ------ | --------------- | --------------------- |
| GET    | /user_role/     | Current user role     |
| GET    | /user_language/ | Current user language |

### Identity & access control

The client never chooses its user id. The server issues an identity — after a verified LTI
launch, or anonymously for standalone users via `POST /session/identity` — as a token signed
with `SECRET_KEY`; the frontend sends it as `Authorization: Bearer <token>` (a token instead of
a cookie, because browsers block third-party cookies in the Moodle iframe). All user data
endpoints act on that identity and ignore any `userid` in the request; only admins may read
another user's data by passing `userid` explicitly.

| Who                         | Can access                                                        |
| --------------------------- | ----------------------------------------------------------------- |
| Any identity                | Own interview, results, survey, language (`/reply`, `/conversation`, `/student/*`, …) |
| Teacher (verified LTI)      | `/dashboard/stats`, `/dashboard/courses` — own course only        |
| Admin (`ADMIN_PASSWORD`)    | All dashboards and courses, `/survey/<id>/results`, other users' data |

Telemetry endpoints (`/log/*`) also require an identity; `/log/interaction` only accepts UI
interaction actions, never server-side or audit actions.

**Admin sessions** are stored server-side (table `admin_session`); the session cookie only
carries a random session id. Logout deletes the session, so a copied cookie stops working too.
Admin sessions end after 8 hours (`ADMIN_SESSION_SECONDS` in `app/identity.py`).

**Admin login throttling:** after 5 failed logins from one IP within 15 minutes, or 50 failed
logins overall (guessing from many IPs), `/admin/login` answers `429` with `Retry-After: 900`,
without checking the password, until the window has passed. While the global limit is reached,
the real admin has to wait too. The limits are constants in `app/routes/admin_routes.py`. To
lift a lockout early, delete the recent `audit_admin_login_failed` rows from `activity_log`.

`tests/test_security.py` calls every registered endpoint without credentials and fails if one
that is not on its explicit public list answers with anything but 401 — new endpoints must be
protected (or consciously added to that list).

**Audit log:** admin logins (incl. failures and throttled attempts) and logouts, every admin-only request (survey
export), every dashboard request (with course scope),
denied accesses, admins reading another user's data, and accepted/rejected LTI launches are
written to `activity_log` (action `audit_*`, hashed client IP) and to the application log (Loki):

```sql
SELECT to_timestamp(timestamp), action, user_id, http_status, value
FROM activity_log WHERE action LIKE 'audit_%' ORDER BY timestamp DESC LIMIT 100;
```

| Method | Path              | Description                                        |
| ------ | ----------------- | -------------------------------------------------- |
| POST   | /session/identity | Get (or create anonymous) identity + token         |
| GET    | /session/identity | Current identity (401 without token)               |
| POST   | /admin/login      | Admin login (server-side check, 429 when throttled) |
| POST   | /admin/logout     | Admin logout                                       |
| GET    | /admin/status     | Whether the session is admin                       |

### LTI

| Method | Path        | Description        |
| ------ | ----------- | ------------------ |
| POST   | /lti/launch | Verified LTI launch → UI with identity token |

### Activity logging

| Method | Path              | Description               |
| ------ | ----------------- | ------------------------- |
| POST   | /log/tab_event    | Tab switch event          |
| POST   | /log/mouse_traces | Mouse movement trace      |
| POST   | /log/page_view    | Page view event           |
| POST   | /log/interaction  | Generic interaction event |

Example requests:

```bash
curl -X POST http://localhost:5000/startConversation \
  -H "Content-Type: application/json" \
  -d '{"language":"en","client":"web","userid":"testuser1"}'

curl -X POST http://localhost:5000/reply \
  -H "Content-Type: application/json" \
  -d '{"message":"I summarize my notes.","client":"web","userid":"testuser1"}'

curl -X POST http://localhost:5000/resetConversation \
  -H "Content-Type: application/json" \
  -d '{"client":"web","userid":"testuser1"}'
```

## 7. Data Model (Core Tables)

| Table                           | Description                              |
| ------------------------------- | ---------------------------------------- |
| users                           | Registered users                         |
| languages                       | Supported languages                      |
| contexts                        | Interview contexts (study situations)    |
| strategy                        | SRL strategy catalogue                   |
| strategy_translation            | Translated strategy labels               |
| strategy_vector                 | pgvector strategy embeddings (RAG)       |
| strategy_embedding              | Embedding metadata                       |
| user_strategy                   | Strategies detected per user run         |
| strategy_evaluation             | Manual or automated strategy evaluations |
| interview_answer                | Raw user answers per context             |
| llm_response                    | LLM outputs stored for audit             |
| state                           | Per-user conversation state machine      |
| conversation_completed_contexts | Completed context tracking               |
| mouse_traces                    | Mouse movement logs                      |
| archive                         | Archived conversation snapshots          |
| activity_log                    | General user interaction events          |
| survey_responses                | SRL-O survey answers                     |

## 8. Testing

### Linting (same checks as the GitLab pipeline)

```bash
# Python (job: python-lint) — run from the repository root
pipx run flake8 backend/app --max-line-length=120 --exclude=__pycache__

# Vue/JS (job: vue-lint)
cd frontend
npm run lint
```

### Unit/integration tests (pytest)

```bash
cd backend
poetry run pytest ../tests/ -v
```

Targeted runs:

```bash
# Interview completion regression
poetry run pytest ../tests/test_interview_completion.py -v -s

# ...and additionally fail if strategies are detected in fewer than half of the contexts
# (requires a reachable LLM; only warns by default)
REQUIRE_STRATEGY_DETECTION=true poetry run pytest ../tests/test_interview_completion.py -v -s

# To view a test user's results: log in as admin, then open
#   http://localhost:5000/#/results?userid=<test user id>
# (only admins may read another user's data)


# RAG
poetry run pytest ../tests/ -v -k rag

# LLM
poetry run pytest ../tests/ -v -k llm

# Aggregate metrics
poetry run pytest ../tests/ -v -k aggregate
```

### Authorization tests

```bash
cd backend
poetry run pytest ../tests/unit ../tests/api -v -rxX
```

- `tests/unit/test_policies.py`: policy functions (`current_identity`, `is_admin`, `is_teacher`, `effective_user_id`, course scope).
- `tests/api/test_permission_matrix.py`: role × endpoint matrix. Every route needs an entry in `ENDPOINTS`; the guard test fails for new routes without one.
- `tests/api/test_authentication.py`: 401 cases (missing, malformed, forged and expired tokens; admin session).
- `tests/api/test_object_access.py`: access to other users' data (IDOR) and course scoping of lists.
- `tests/api/test_privilege_escalation.py`: role, user id, course or admin flag in the payload.

These tests use real signed tokens and a real admin login (fixtures `make_user` and `client_as` in `tests/conftest.py`). Each test runs in a transaction that is rolled back afterwards (`isolated_db`). Known weaknesses are marked `xfail(strict=True)`: when one gets fixed, the test turns XPASS and fails until the marker is removed.

### Curl smoke tests

```bash
# verify backend
curl http://localhost:5000/

# verify model endpoint (if local)
curl http://localhost:11434/api/tags
```

### Load testing (Locust)

```bash
cd backend
poetry run locust -f ../tests/locustfile.py --host=http://localhost:5000
```

Then open: http://localhost:8089

## 9. Operational Notes

- For dozens of concurrent users, monitor:
  - DB connections
  - request latency of /reply
  - activity_log and mouse_traces growth
- Rotate logs (`backend/logs/api.log` rotates at 1 MB, 5 backups kept).
- Keep interview protocol and prompts versioned; changes directly affect LLM behavior.
- `SECRET_KEY` must be changed from the default before any production deployment.

### Abuse limits (LLM budget)

Every `/reply` triggers several LLM calls, so it is limited:

| Limit | Where | Value |
| --- | --- | --- |
| Message length | API (413 `message_too_long`) and input field | 2000 characters |
| Messages per user | API (429 `rate_limited`, `Retry-After: 60`) | 10 per minute |
| Messages per interview | API (429 `interview_quota_reached`) | 50 |
| Requests per client IP | nginx (429) | `/reply` 60/min (burst 30); `/startConversation`, `/resetConversation`, `/session/identity` 20/min (burst 40) |
| Request body | nginx (413) | 32 KB for the endpoints above |

The per-user limits live in `backend/app/routes/chat_routes.py`; the UI shows a message when one
is reached. The per-IP limits are deliberately generous (many students may share one IP via the
campus network or VPN) and mainly stop mass abuse with freshly created anonymous identities.

LLM credentials (`API_KEY`, `EMBEDDING_TOKEN`) stay on the server and are only sent as
`Authorization` header; they are never sent over plain `http://` to a non-local host
(use an `https://` `BASE_URL`).

### Grafana (logs)

Grafana is not published through nginx: the logs contain interview content and audit data. It
listens on `127.0.0.1:3000` of the server only. Access it through an SSH tunnel:

```bash
ssh -L 3000:localhost:3000 <user>@<server>
# then open http://localhost:3000/grafana/
```

`GRAFANA_PASSWORD` must be set in `.env` (docker compose refuses to start otherwise). Grafana only
applies it when its data volume is created; to change the password of an existing installation:

```bash
docker compose exec grafana grafana cli admin reset-admin-password '<new password>'
```
