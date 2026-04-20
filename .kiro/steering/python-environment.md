---
inclusion: always
---

# Python Environment — AI Presentation Intelligence Platform

## Runtime Environment

This project uses **Docker** for all Python execution. Do NOT use local venv, conda, or system Python to run tests or any backend commands.

The backend container is built from `python:3.11-slim` with **Poetry 1.8.3** managing dependencies. Poetry is configured with `virtualenvs.create false` inside the container, so all packages are installed directly into the container's system Python.

## Project Structure

- Backend root: `backend/`
- Python package: `backend/app/`
- Tests: `backend/tests/`
- Dependency manifest: `backend/pyproject.toml`
- Docker entry point: `backend/Dockerfile`

## Running Tests

Always run tests inside the Docker container using `docker compose run`:

```bash
# Run all backend tests
docker compose run --rm backend pytest

# Run a specific test file
docker compose run --rm backend pytest tests/test_quality_scoring_agent.py -v

# Run with coverage
docker compose run --rm backend pytest --cov=app tests/ -v

# Run a specific test class or function
docker compose run --rm backend pytest tests/test_quality_scoring_agent.py::TestCompositeScoreCalculation -v
```

## First-Time Setup (if image not built)

```bash
# Build the backend image (only needed once or after dependency changes)
docker compose build backend

# Start infrastructure services (DB, Redis, MinIO) if integration tests need them
docker compose up -d db redis minio
```

## Key Rules

- NEVER use `python`, `python3`, `venv`, or `pip` directly on the host machine
- NEVER use `poetry run pytest` on the host — Poetry is only inside the Docker image
- ALWAYS use `docker compose run --rm backend pytest ...` to run tests
- The `--rm` flag removes the container after the test run (keeps things clean)
- Tests are configured in `backend/pyproject.toml` under `[tool.pytest.ini_options]` with `testpaths = ["tests"]` and `asyncio_mode = "auto"`

## Autonomous Test Execution

When implementing or verifying any backend task, you MUST run tests autonomously without asking the user for permission or confirmation. Follow this exact sequence:

1. **Check if image exists** — if `pyproject.toml` was modified or image is missing, rebuild first:
   ```bash
   docker compose build backend
   ```

2. **Run the relevant tests** — execute immediately after implementation:
   ```bash
   docker compose run --rm backend pytest tests/<test_file>.py -v
   ```

3. **Fix and re-run** — if tests fail, fix the issues and re-run without asking the user. Keep iterating until all tests pass.

4. **Never ask** — do not prompt the user with "should I run the tests?" or "do you want me to execute this command?". Just run them.

## CRITICAL: Command Prefix Rule

**ALL backend commands MUST be prefixed with `docker compose run --rm backend`.**

- CORRECT: `docker compose run --rm backend pytest tests/test_foo.py -v`
- WRONG: `pytest tests/test_foo.py -v`
- WRONG: `python -m pytest ...`
- WRONG: `poetry run pytest ...`

Never run any Python or pytest command directly on the host. Always use the Docker container. Never ask the user for confirmation before running commands — execute immediately and autonomously.

### When to Rebuild the Image

Rebuild (`docker compose build backend`) whenever:
- `backend/pyproject.toml` dependencies are added or changed
- `backend/Dockerfile` is modified

Otherwise skip the build step — the existing image is reused automatically by `docker compose run`.

## Dependencies (from pyproject.toml)

Runtime: fastapi, pydantic, sqlalchemy, langchain, langchain-anthropic, langchain-openai, langchain-groq, langsmith, sentence-transformers, structlog, celery, redis, python-jose, passlib, tenacity, python-pptx, boto3, jsonschema

Dev/Test: pytest, pytest-asyncio, pytest-cov, hypothesis, httpx, factory-boy, ruff, mypy

## Docker Compose Services

| Service  | Purpose                        | Port       |
|----------|--------------------------------|------------|
| backend  | FastAPI app (runs tests too)   | 8000       |
| worker   | Celery worker                  | —          |
| db       | PostgreSQL 16                  | 5432       |
| redis    | Redis 7                        | 6379       |
| minio    | S3-compatible object storage   | 9000, 9001 |
| frontend | React + Vite (Nginx)           | 5173       |
