# AI Presentation Intelligence Platform

A full-stack AI-powered platform that generates professional, enterprise-grade presentations from a single topic input. The system uses a 10-agent pipeline to classify, design, research, enrich, and generate structured slide decks with charts, tables, comparisons, and rich visuals — all rendered in real-time via Server-Sent Events.

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
- **10-agent AI pipeline** — industry classification, design spec generation, storyboarding, research, data enrichment, prompt engineering, LLM generation, validation, visual refinement, and quality scoring
- **User theme selection** — choose from 4 enterprise themes via a visual picker, or let the system auto-detect based on industry and audience
- **Design Agent** — LLM-driven color palette, font pairing, and visual motif generation tailored to each topic
- **Real-time streaming** — slides appear progressively via SSE as they are generated
- **Rich slide types** — title, content, chart (bar/line/pie/area/scatter/donut), table, comparison, metric/KPI
- **PPTX export** — enterprise-grade PowerPoint export via a dedicated Node.js pptx-service using pptxgenjs
- **Quality scoring** — automatic quality assessment with feedback loop (re-generates if score < 8.0)
- **Provider failover** — Claude → OpenAI → Groq with circuit breaker and automatic fallback
- **Multi-tenant** — JWT-based auth with role-based access control (admin / member / viewer)
- **LangSmith tracing** — full observability for all LLM calls
- **Interactive viewer** — fullscreen mode, keyboard navigation, speaker notes panel, dot navigation
- **Checkpoint recovery** — pipeline resumes from the last completed agent on failure
- **Cost control** — configurable per-request LLM call limits and spend ceiling

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│  PresentationGenerator → ThemeSelector → SSE → SlideViewer      │
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
│  ① Industry      ② Design        ③ Storyboarding                │
│    Classifier  →   Agent       →   Agent                     →  │
│                                                                  │
│  ④ Research      ⑤ Data          ⑥ Prompt                       │
│    Agent       →   Enrichment  →   Engineering               →  │
│                                                                  │
│  ⑦ LLM Provider  ⑧ Validation   ⑨ Visual        ⑩ Quality      │
│    (Claude/GPT) →  Agent       →   Refinement  →   Scoring      │
│                                                                  │
│  [Feedback Loop: if score < 8.0, re-run ⑦→⑩ up to 2 times]    │
└──────────────────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│  Infrastructure                                                  │
│  PostgreSQL 16 │ Redis 7 │ MinIO (S3) │ pptx-service │ LangSmith│
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
| LLM Providers | Anthropic Claude, OpenAI GPT-4o, Groq Llama-3.3-70b |
| Observability | LangSmith + structlog |
| Object Storage | MinIO (S3-compatible) |
| Auth | JWT (python-jose) + bcrypt |
| Runtime | Python 3.11 + Poetry 1.8 |

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

### PPTX Service
| Component | Technology |
|-----------|-----------|
| Runtime | Node.js + Express |
| PPTX Generation | pptxgenjs |
| PDF Preview | LibreOffice headless + pdftoppm |

### Infrastructure
| Service | Purpose | Port |
|---------|---------|------|
| backend | FastAPI app | 8000 |
| worker | Celery worker | — |
| pptx-service | Node.js PPTX builder | 3001 |
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
│   │   ├── agents/              # 10-agent pipeline
│   │   │   ├── pipeline_orchestrator.py
│   │   │   ├── industry_classifier.py
│   │   │   ├── design_agent.py
│   │   │   ├── storyboarding.py
│   │   │   ├── research.py
│   │   │   ├── data_enrichment.py
│   │   │   ├── prompt_engineering.py
│   │   │   ├── layout_engine.py
│   │   │   ├── validation.py
│   │   │   ├── visual_refinement.py
│   │   │   ├── quality_scoring.py
│   │   │   └── conflict_resolution.py
│   │   ├── api/v1/              # REST API endpoints
│   │   │   ├── presentations.py
│   │   │   ├── auth.py
│   │   │   ├── health.py
│   │   │   ├── slide_editing.py
│   │   │   ├── schema_versioning.py
│   │   │   └── export_templates_admin.py
│   │   ├── core/                # Config, security
│   │   ├── db/                  # Models, sessions
│   │   ├── middleware/          # RBAC, audit, sanitization, security headers, tenant, API versioning
│   │   ├── services/            # LLM provider, streaming, cache, cost tracking, rate limiter
│   │   └── worker/              # Celery tasks
│   ├── alembic/                 # DB migrations
│   ├── tests/                   # pytest test suite
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── slides/          # TitleSlide, ChartSlide, TableSlide, ComparisonSlide, MetricSlide
│       │   ├── PresentationGenerator.tsx
│       │   ├── ThemeSelector.tsx
│       │   ├── PresentationWorkflow.tsx
│       │   ├── ProgressiveSlideViewer.tsx
│       │   ├── ProgressIndicator.tsx
│       │   └── DownloadButton.tsx
│       ├── hooks/               # useSSEStream
│       ├── services/            # API client (axios)
│       ├── styles/              # Design tokens (spacing, typography, themes)
│       ├── types/               # TypeScript interfaces
│       └── utils/               # themeUtils, layoutEngine
├── pptx-service/
│   ├── builder.js               # pptxgenjs slide builder
│   ├── server.js                # Express server (/build, /preview)
│   ├── icons.js                 # SVG icon renderer
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── ARCHITECTURE.md
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
LLM_PRIMARY_PROVIDER=claude
LLM_FALLBACK_PROVIDERS=openai,groq

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
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `MAX_LLM_CALLS_PER_REQUEST` | `4` | Max LLM calls per generation |
| `COST_CEILING_USD` | `1.0` | Max spend per request |
| `PPTX_SERVICE_URL` | `http://pptx-service:3001` | pptx-service endpoint |

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
# Generate a presentation (with optional theme)
POST /api/v1/presentations
Authorization: Bearer <token>
{ "topic": "Healthcare sector market analysis", "theme": "corporate" }
# theme is optional: corporate | executive | professional | dark-modern
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
GET /api/v1/presentations/{id}/export/status?job_id=<job_id>

# Cancel a running job
DELETE /api/v1/jobs/{job_id}
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

The pipeline runs 10 agents sequentially:

```
 1. Industry Classifier  (≤15s)   — Detects industry, audience, template, theme
 2. Design Agent         (≤20s)   — Generates color palette, fonts, motif via LLM
 3. Storyboarding        (≤10s)   — Builds section structure and slide plan
 4. Research             (≤60s)   — Gathers insights, risks, opportunities via LLM
 5. Data Enrichment      (≤20s)   — Generates charts, tables, KPI metrics
 6. Prompt Engineering   (≤5s)    — Optimises prompts per LLM provider
 7. LLM Provider         (≤300s)  — Generates full Slide_JSON via Claude/GPT/Groq
 8. Validation           (≤5s)    — Validates schema, auto-corrects errors
 9. Visual Refinement    (≤90s)   — Post-validation visual polish
10. Quality Scoring      (≤10s)   — Scores 5 dimensions; triggers feedback loop if < 8.0
```

**Quality dimensions:** Content Depth (25%) · Visual Appeal (20%) · Structure Coherence (25%) · Data Accuracy (15%) · Clarity (15%)

**Feedback loop:** If composite score < 8.0, agents 7-10 re-run automatically (max 2 retries).

---

## Slide Types

| Type | Visual Hint | Description |
|------|-------------|-------------|
| `title` | `centered` | Title + subtitle with decorative background |
| `content` | `bullet-left` | Numbered bullets with icon and highlight box |
| `chart` | `split-chart-right` | Bar / line / pie / area / scatter / donut chart with stats panel |
| `table` | `split-table-left` | Data table with colored header row |
| `comparison` | `two-column` | Side-by-side A vs B with VS divider |
| `metric` | `highlight-metric` | Big KPI number with trend badge and context bullets |

---

## Themes

Users can select a theme from the UI or let the system auto-detect based on industry and audience.

| Theme | Primary | Style | Auto-selected for |
|-------|---------|-------|-------------------|
| `corporate` | Navy `#002855` | Clean enterprise, monochromatic navy-white | Default for most industries |
| `executive` | Navy `#003366` | Boardroom-ready with gold accent | Executive audiences, consulting |
| `professional` | Green `#86BC25` | Modern professional services | Finance, insurance, analyst audiences |
| `dark-modern` | Purple `#6C63FF` | Dark background, vibrant accents | Technology, fintech, technical audiences |

Each theme includes a full color palette (primary, secondary, accent, background, text, surface, border), chart color series, and font pairing. The Design Agent further refines colors per topic using LLM-generated palettes.

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

### Run frontend tests

```bash
cd frontend && npm run test
```

### Rebuild after dependency changes

```bash
docker compose build backend
docker compose up -d
```

### View logs

```bash
docker compose logs -f           # All services
docker compose logs -f worker    # Agent pipeline
docker compose logs -f backend   # API server
```

---

## Testing

| Test File | Coverage |
|-----------|---------|
| `test_pipeline_orchestrator.py` | Full pipeline, feedback loop, checkpoints |
| `test_pptx_export.py` | PPTX generation, all themes, all slide types |
| `test_presentations_api.py` | API endpoints, rate limiting, status progression |
| `test_quality_scoring_agent.py` | All 5 scoring dimensions |
| `test_validation_agent.py` | Schema validation, auto-corrections |
| `test_data_enrichment_agent.py` | Data generation, chart types |
| `test_research_agent.py` | Research findings structure |
| `test_industry_classifier.py` | Classification, theme selection |
| `test_layout_engine.py` | Visual hints, density, layout scoring |
| `test_background_jobs.py` | Celery tasks, idempotency, retries |
| `test_caching_layer.py` | Cache keys, hit/miss, analytics |
| `test_advanced_integration.py` | Slide snapshots, multi-tenant isolation |
| `test_observability.py` | Agent tracing, provider failover |

---

## License

MIT
