# Contributing

## Development Setup

### Backend

```bash
cd backend
poetry install
cp ../env.example .env   # adjust values
poetry run python -m app.database.setup_no_embed
poetry run python main.py
```

### Frontend

```bash
cd frontend
npm install
npm run watch   # rebuilds on file change
```

### Docker Compose (full stack)

```bash
cp env.example .env
docker compose -f develop.docker-compose.yml up postgres-dev api-dev
```

## Code Style

**Python** — flake8, max line length 120:

```bash
cd backend
poetry run flake8 app --max-line-length=120 --exclude=__pycache__
```

**JavaScript / Vue** — ESLint:

```bash
cd frontend
npm run lint
```

## Tests

```bash
cd backend
poetry run pytest ../tests/ -v
```

Individual suites:

```bash
poetry run pytest ../tests/test_routes.py -v
poetry run pytest ../tests/test_strategy_detection.py -v
```

Most tests require a running PostgreSQL instance (see `.env`) and `DISABLE_LLM=true` to skip Ollama.

## Submitting Changes

1. Branch off `develop` (or `main` if there is no active `develop`).
2. Open a Merge Request against `main` via GitLab.
3. Ensure the CI pipeline (lint + test) passes.
4. Describe what the MR changes and why in the description.

## Reporting Issues

Open an issue in GitLab and include steps to reproduce, expected behaviour, and actual behaviour.
