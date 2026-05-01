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
srl-chat/
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

SECRET_KEY=change-me-in-production

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
npm install
npm run build

cd ../backend
poetry run python main.py
```

### LTI deployment

- Launch endpoint: /lti/launch
- UI endpoint: /lti/ui
- Configure LMS external tool with launch URL, key, and secret
- Ensure HTTPS in production LMS setups

For detailed Moodle-centric setup, see [README-LTI.md](README-LTI.md).

### Docker Compose

```bash
cp env.example .env

# Dev stack
docker compose -f develop.docker-compose.yml up postgres-dev api-dev

# Prod-like stack
docker compose build --no-cache
docker compose up -d
```

## 6. API Endpoints

### Chat

| Method | Path | Description |
|--------|------|-------------|
| POST | /startConversation | Start a new interview session |
| POST | /reply | Submit a user message |
| POST | /resetConversation | Reset current session |
| GET | /conversation | Retrieve conversation history |

### Survey

| Method | Path | Description |
|--------|------|-------------|
| GET | /survey/`<id>` | Load survey definition |
| POST | /survey/`<id>`/submit | Submit survey answers |
| GET | /survey/`<id>`/results | Retrieve survey results |
| GET | /student/results | Student interview results |
| GET | /student/interview_runs | Student run list |

### Protocol editor

| Method | Path | Description |
|--------|------|-------------|
| GET | /protocols | List available protocols |
| POST | /protocols | Create a new protocol |
| GET | /protocols/`<name>` | Get a protocol |
| PUT | /protocols/`<name>` | Update a protocol |
| DELETE | /protocols/`<name>` | Delete a protocol |
| GET | /protocols/`<name>`/export | Export protocol as JSON |
| POST | /protocols/import | Import protocol from JSON |

### Dashboard

| Method | Path | Description |
|--------|------|-------------|
| GET | /dashboard/stats | Aggregated interview statistics |
| GET | /dashboard/courses | Course list |

### User

| Method | Path | Description |
|--------|------|-------------|
| GET | /user_role/ | Current user role |
| GET | /user_language/ | Current user language |

### LTI

| Method | Path | Description |
|--------|------|-------------|
| POST | /lti/launch | LTI launch handler |
| GET | /lti/ui | LTI-embedded UI |

### Activity logging

| Method | Path | Description |
|--------|------|-------------|
| POST | /log/tab_event | Tab switch event |
| POST | /log/mouse_traces | Mouse movement trace |
| POST | /log/page_view | Page view event |
| POST | /log/interaction | Generic interaction event |

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

| Table | Description |
|-------|-------------|
| users | Registered users |
| languages | Supported languages |
| contexts | Interview contexts (study situations) |
| strategy | SRL strategy catalogue |
| strategy_translation | Translated strategy labels |
| strategy_vector | pgvector strategy embeddings (RAG) |
| strategy_embedding | Embedding metadata |
| user_strategy | Strategies detected per user run |
| strategy_evaluation | Manual or automated strategy evaluations |
| interview_answer | Raw user answers per context |
| llm_response | LLM outputs stored for audit |
| state | Per-user conversation state machine |
| conversation_completed_contexts | Completed context tracking |
| mouse_traces | Mouse movement logs |
| archive | Archived conversation snapshots |
| activity_log | General user interaction events |
| survey_responses | SRL-O survey answers |

## 8. Testing

### Unit/integration tests (pytest)

```bash
cd backend
poetry run pytest ../tests/ -v
```

Targeted runs:

```bash
# Interview completion regression
poetry run pytest ../tests/test_interview_completion.py -v -s

# Set in browser console to see results in the /results page:
localStorage.setItem("srl_userid", "test_interview_bot")
location.reload()


# RAG
poetry run pytest ../tests/ -v -k rag

# LLM
poetry run pytest ../tests/ -v -k llm

# Aggregate metrics
poetry run pytest ../tests/ -v -k aggregate
```

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
