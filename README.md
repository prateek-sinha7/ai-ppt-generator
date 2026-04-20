# AI Presentation Intelligence Platform

A full-stack AI-powered platform that generates professional, consulting-grade presentations from a single topic input. The system uses a multi-agent pipeline to research, enrich, and generate structured slide decks with charts, tables, comparisons, and rich visuals — all rendered in real-time via Server-Sent Events.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Agent Pipeline](#agent-pipeline)
- [Slide Types](#slide-types)
- [Themes](#themes)
- [Development](#development)
- [Testing](#testing)

---

## Features

- **One-input generation** — enter a topic, get a full professional presentation
- **Multi-agent AI pipeline** — 8 specialized agents handle classification, research, data enrichment, prompt engineering, generation, validation, and quality scoring
- **Real-time streaming** — slides appear progressively via SSE as they are generated
- **Rich slide types** — title, content, chart (bar/line/pie), table, comparison, metric/KPI
- **Visual themes** — McKinsey, Deloitte, Dark Modern
- **Interactive viewer** — fullscreen mode, keyboard navigation, speaker notes panel, dot navigation
- **Download PPTX** — export the generated presentation as a PowerPoint file
- **Quality scoring** — automatic quality assessment with feedback loop (re-generates if score < 8)
- **Provider failover** — Claude → OpenAI → GROQ with automatic fallback
- **Multi-tenant** — JWT-based auth with role-based access control
- **LangSmith tracing** — full observability for all LLM calls

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│  PresentationGenerator → SSE Stream → ProgressiveSlideViewer    │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼────────────────────────────────────┐
│                     Backend (FastAPI)                            │
│  POST /presentations → Celery Task → Pipeline Orchestrator       │
│  GET  /presentations/{id}/stream → Redis Streams → SSE           │
└──────────┬──────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│                  Multi-Agent Pipeline (Celery Worker)            │
│                                                                  │
│  Industry       Storyboarding    Research      Data              │
│  Classifier  →  Agent        →   Agent     →   Enrichment    →  │
│                                                                  │
│  Prompt         LLM Provider     Validation    Quality           │
│  Engineering →  (Claude/GPT) →   Agent     →   Scoring          │
└──────────────────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│  Infrastructure                                                  │
│  PostgreSQL 16 │ Redis 7 │ MinIO (S3) │ LangSmith               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| API Framework | FastAPI 0.111 + Uvicorn |
| Task Queue | Celery 5.4 + Redis |
| Database | PostgreSQL 16 + SQLAlchemy 2 (async) |
| Migrations | Alembic |
| AI Orchestration | LangChain 0.2 |
| LLM Providers | Anthropic Claude, OpenAI GPT-4o, Groq Llama |
| Observability | LangSmith |
| Object Storage | MinIO (S3-compatible) |
| PPTX Export | python-pptx |
| Auth | JWT (python-jose) + bcrypt |
| Logging | structlog |
| Runtime | Python 3.11 + Poetry |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | React 18 + TypeScript |
| Build Tool | Vite 5 |
| Styling | Tailwind CSS 3 |
| Charts | Recharts 2 |
| Icons | Lucide React |
| Drag & Drop | dnd-kit |
| HTTP Client | Axios |
| Streaming | EventSource (SSE) |

### Infrastructure
| Service | Purpose | Port |
|---------|---------|------|
| backend | FastAPI app | 8000 |
| worker | Celery worker | — |
| db | PostgreSQL 16 | 5432 |
| redis | Broker + cache + streams | 6379 |
| minio | PPTX file storage | 9000, 9001 |
| frontend | React + Nginx | 5173 |

---

## Project Structure

```
ai-ppt-generator/
├── backend/
│   ├── app/
│   │   ├── agents/              # Multi-agent pipeline
│   │   │   ├── pipeline_orchestrator.py
│   │   │   ├── industry_classifier.py
│   │   │   ├── storyboarding.py
│   │   │   ├── research.py
│   │   │   ├── data_enrichment.py
│   │   │   ├── prompt_engineering.py
│   │   │   ├── validation.py
│   │   │   └── quality_scoring.py
│   │   ├── api/v1/              # REST API endpoints
│   │   │   ├── presentations.py
│   │   │   ├── auth.py
│   │   │   └── health.py
│   │   ├── core/                # Config, security
│   │   ├── db/                  # Models, sessions
│   │   ├── middleware/          # RBAC, audit, sanitization
│   │   ├── services/            # LLM provider, streaming, cache
│   │   └── worker/              # Celery tasks
│   ├── alembic/                 # DB migrations
│   ├── tests/                   # pytest test suite
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── slides/          # TitleSlide, ChartSlide, TableSlide, etc.
│       │   ├── ProgressIndicator.tsx
│       │   ├── ProgressiveSlideViewer.tsx
│       │   ├── PresentationWorkflow.tsx
│       │   └── DownloadButton.tsx
│       ├── hooks/               # useSSEStream
│       ├── services/            # API client
│       ├── styles/              # Design tokens, themes
│       └── types/               # TypeScript interfaces
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- An API key from at least one LLM provider:
  - [Anthropic Claude](https://console.anthropic.com/) (recommended)
  - [OpenAI](https://platform.openai.com/)
  - [Groq](https://console.groq.com/)

### 1. Clone and configure

```bash
git clone <repo-url>
cd ai-ppt-generator
cp .env.example .env
```

### 2. Set your API keys in `.env`

```env
# Primary LLM provider
LLM_PRIMARY_PROVIDER=claude
LLM_FALLBACK_PROVIDERS=openai,groq

# API Keys
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-...          # optional
GROQ_API_KEY=gsk_...           # optional

# LangSmith (optional — for observability)
LANGSMITH_API_KEY=lsv2_...
LANGCHAIN_TRACING_V2=true
```

### 3. Start all services

```bash
docker compose up -d
```

### 4. Run database migrations

```bash
docker compose exec backend alembic upgrade head
```

### 5. Open the app

- **Frontend:** http://localhost:5173
- **API docs:** http://localhost:8000/docs
- **MinIO console:** http://localhost:9001 (minioadmin / minioadmin)

---

## Configuration

All configuration is via environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PRIMARY_PROVIDER` | `claude` | Primary LLM: `claude`, `openai`, `groq` |
| `LLM_FALLBACK_PROVIDERS` | `openai,groq` | Comma-separated fallback list |
| `ANTHROPIC_API_KEY` | — | Claude API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `GROQ_API_KEY` | — | Groq API key |
| `LANGSMITH_API_KEY` | — | LangSmith tracing key |
| `LANGCHAIN_TRACING_V2` | `false` | Enable LangSmith tracing |
| `SECRET_KEY` | — | JWT signing secret (change in production) |
| `DATABASE_URL` | postgres://... | PostgreSQL connection string |
| `REDIS_URL` | redis://redis:6379/0 | Redis connection string |
| `MAX_LLM_CALLS_PER_REQUEST` | `4` | Cost control limit |
| `COST_CEILING_USD` | `1.0` | Max spend per request |

---

## API Reference

### Authentication

```bash
# Register
POST /api/v1/auth/register
{ "email": "user@example.com", "password": "..." }

# Login
POST /api/v1/auth/login
{ "email": "user@example.com", "password": "..." }
# Returns: { "access_token": "...", "refresh_token": "..." }
```

### Presentations

```bash
# Generate a presentation
POST /api/v1/presentations
Authorization: Bearer <token>
{ "topic": "Healthcare sector market analysis" }
# Returns: { "job_id": "...", "presentation_id": "..." }

# Stream generation progress (SSE)
GET /api/v1/presentations/{id}/stream?token=<jwt>

# Poll status
GET /api/v1/presentations/{id}/status

# Get completed presentation
GET /api/v1/presentations/{id}

# Regenerate
POST /api/v1/presentations/{id}/regenerate

# Export to PPTX
POST /api/v1/presentations/{id}/export
# Returns: { "job_id": "..." }

# Poll export status
GET /api/v1/presentations/{id}/export/status?job_id=<job_id>
# Returns: { "status": "completed", "download_url": "..." }
```

### SSE Event Types

| Event | Description |
|-------|-------------|
| `agent_start` | An agent has begun processing |
| `agent_complete` | An agent finished with elapsed time |
| `slide_ready` | A single slide is available for rendering |
| `quality_score` | Quality scoring result (composite + dimensions) |
| `complete` | Pipeline finished successfully |
| `error` | Pipeline failed with error details |

---

## Agent Pipeline

The pipeline runs 8 agents sequentially:

```
1. Industry Classifier  (≤15s)  — Detects industry, audience, template, theme
2. Storyboarding        (≤10s)  — Builds section structure and slide plan
3. Research             (≤30s)  — Gathers insights, risks, opportunities
4. Data Enrichment      (≤20s)  — Generates charts, tables, KPI metrics
5. Prompt Engineering   (≤5s)   — Optimises prompts per LLM provider
6. LLM Provider         (≤150s) — Generates full Slide_JSON via Claude/GPT/Groq
7. Validation           (≤5s)   — Validates schema, auto-corrects errors
8. Quality Scoring      (≤10s)  — Scores 5 dimensions; triggers feedback loop if < 8.0
```

**Quality dimensions:** Content Depth (25%) · Visual Appeal (20%) · Structure Coherence (25%) · Data Accuracy (15%) · Clarity (15%)

**Feedback loop:** If composite score < 8.0, agents 6–8 re-run automatically (max 2 retries).

---

## Slide Types

| Type | Visual Hint | Description |
|------|-------------|-------------|
| `title` | `centered` | Title + subtitle with decorative background |
| `content` | `bullet-left` | Numbered bullets with icon and highlight box |
| `chart` | `split-chart-right` | Bar / line / pie chart with stats panel |
| `table` | `split-table-left` | Data table with colored header row |
| `comparison` | `two-column` | Side-by-side A vs B with VS divider |
| `metric` | `highlight-metric` | Big KPI number with animated counter and trend |

---

## Themes

| Theme | Primary Color | Style |
|-------|--------------|-------|
| `mckinsey` | Navy `#003366` | Classic consulting, white background |
| `deloitte` | Green `#86BC25` | Modern professional, clean |
| `dark-modern` | Purple `#6C63FF` | Dark background, vibrant accents |

---

## Development

### Run backend tests

```bash
docker compose run --rm backend pytest tests/ -v
```

### Run specific test file

```bash
docker compose run --rm backend pytest tests/test_pipeline_orchestrator.py -v
```

### Run with coverage

```bash
docker compose run --rm backend pytest --cov=app tests/ -v
```

### Rebuild after dependency changes

```bash
docker compose build backend
docker compose up -d
```

### View logs

```bash
# All services
docker compose logs -f

# Worker only (agent pipeline)
docker compose logs -f worker

# Backend only
docker compose logs -f backend
```

---

## Testing

The test suite covers:

| Test File | Coverage |
|-----------|---------|
| `test_pipeline_orchestrator.py` | Full pipeline, feedback loop, checkpoints |
| `test_background_jobs.py` | Celery tasks, idempotency, retries |
| `test_quality_scoring_agent.py` | All 5 scoring dimensions |
| `test_validation_agent.py` | Schema validation, auto-corrections |
| `test_data_enrichment_agent.py` | Data generation, chart types |
| `test_research_agent.py` | Research findings structure |

---

## License

MIT
