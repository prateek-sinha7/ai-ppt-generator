# AI Presentation Intelligence Platform — Client Demo Document

**Phase 1 — Initial Release**
*Prepared for Client Demo · April 23, 2026*

---

## 1. Executive Summary

The AI Presentation Intelligence Platform is a full-stack, enterprise-grade system that transforms a single text topic into a complete, professionally designed PowerPoint presentation — automatically. The user types a topic, selects a visual theme, and the system does the rest: classifying the industry, designing the visual identity, planning the narrative structure, researching the domain, generating rich content, scoring quality, and exporting a pixel-perfect PPTX file — all in real time.

This document covers the complete system architecture, every agent in the pipeline, how LLMs are integrated, the end-to-end data flow, and how the final presentation is rendered and delivered.

> **This is Phase 1 — the initial version of the platform.** Future phases will introduce LLM-driven layout variants and theme factories for dynamic presentation styling (detailed in Section 9).

---

## 2. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite 5 |
| Backend API | FastAPI 0.111 + Python 3.11 |
| Task Queue | Celery 5.4 + Redis 7 |
| Database | PostgreSQL 16 + SQLAlchemy 2 (async) |
| AI Orchestration | LangChain 0.2 |
| LLM Providers | Anthropic Claude · OpenAI GPT-4o · Groq Llama-3.3-70b |
| Observability | LangSmith + structlog |
| PPTX Rendering | Node.js + pptxgenjs (dedicated microservice) |
| Object Storage | MinIO (S3-compatible) |
| Auth | JWT + bcrypt + RBAC |
| Containerization | Docker Compose (7 services) |

---

## 3. System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     React Frontend (Port 5173)                    │
│  PresentationGenerator → ThemeSelector → SSE → SlideViewer       │
└────────────────────────────┬─────────────────────────────────────┘
                             │  HTTP REST + Server-Sent Events
┌────────────────────────────▼─────────────────────────────────────┐
│                   FastAPI Backend (Port 8000)                     │
│  Security · CORS · Audit · Tenant · RBAC Middleware Stack         │
│  POST /presentations → Celery Task                                │
│  GET  /presentations/{id}/stream → Redis Stream → SSE             │
└──────────────────────────┬───────────────────────────────────────┘
                           │  Celery Task
┌──────────────────────────▼───────────────────────────────────────┐
│              Multi-Agent Pipeline (Celery Worker)                 │
│                                                                   │
│  ① Industry Classifier  →  ② Design Agent  →  ③ Storyboarding   │
│  ④ Research Agent       →  ⑤ Data Enrichment → ⑥ Prompt Eng.   │
│  ⑦ LLM Provider         →  ⑧ Validation    →  ⑨ Visual Refine  │
│  ⑩ Quality Scoring                                               │
│                                                                   │
│  [Feedback Loop: score < 8.0 → re-run ⑦→⑩, max 2 retries]      │
└──────────────────────────┬───────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  PostgreSQL 16       Redis 7            MinIO (S3)
  (data + state)   (queue + SSE)      (PPTX exports)
                           │
                    ┌──────▼──────┐
                    │ pptx-service│  Node.js + pptxgenjs
                    │  Port 3001  │  POST /build  → PPTX buffer
                    └─────────────┘  POST /preview → JPG images
```

### Infrastructure Services

| Service | Role | Port |
|---|---|---|
| backend | FastAPI API + Celery worker | 8000 |
| worker | Celery background task executor | — |
| db | PostgreSQL 16 (data persistence) | 5432 |
| redis | Celery broker + SSE streams + cache | 6379 |
| minio | S3-compatible PPTX file storage | 9000/9001 |
| pptx-service | Node.js PPTX renderer | 3001 |
| frontend | React + Nginx | 5173 |

---

## 4. End-to-End Workflow

### Step 1 — User Input

The user opens the web app, logs in (JWT auth), and enters a topic (e.g., *"Healthcare sector market analysis"*). They optionally select one of four visual themes: **Corporate**, **Executive**, **Professional**, or **Dark Modern**.

### Step 2 — API Request

```http
POST /api/v1/presentations
{ "topic": "Healthcare sector market analysis", "theme": "executive" }
```

The backend:
- Creates a `Presentation` record in PostgreSQL (status = `queued`)
- Creates a `PipelineExecution` record
- Enqueues a `generate_presentation_task` Celery job
- Returns `{ presentation_id, job_id }` immediately

### Step 3 — Real-Time Streaming

The frontend opens an SSE connection:

```http
GET /api/v1/presentations/{id}/stream?token=<jwt>
```

The backend reads from a Redis Stream (`stream:presentation:{id}`) and forwards events to the browser as they arrive. The user sees a live progress bar and slides appearing one by one.

### Step 4 — 10-Agent Pipeline Executes

The Celery worker picks up the task and runs the pipeline sequentially (detailed in Section 5).

### Step 5 — Completion

When the pipeline finishes:
- All slides are saved to PostgreSQL (JSONB column)
- Slide JSON is cached in Redis (6-hour TTL)
- A `complete` SSE event is sent to the frontend
- The frontend transitions to the interactive slide viewer

### Step 6 — PPTX Export

The user clicks "Download PPTX":

```http
POST /api/v1/presentations/{id}/export
```

- A `export_pptx_task` Celery job is enqueued
- The worker calls `pptx-service` (Node.js) with the slides + design spec + theme
- pptx-service builds the PPTX using pptxgenjs
- The file is uploaded to MinIO
- A signed download URL (1-hour TTL) is returned to the user

---

## 5. The 10-Agent Pipeline — Deep Dive

Each agent runs sequentially. The Pipeline Orchestrator manages state, enforces latency budgets, handles circuit breakers, and persists checkpoints to the database after every agent so the pipeline can resume from the last completed step on failure.

---

### Agent 1 — Industry Classifier

**Budget:** 15 seconds | **LLM:** Only as last resort

**What it does:** Automatically detects the industry from the topic — the user never sees or interacts with this step.

**Three-step classification:**

1. **Keyword Matching** — Fast, deterministic. Checks topic against seed term sets for 11 industries (healthcare, finance, fintech, technology, retail, education, manufacturing, logistics, real estate, insurance, automobile).
2. **Semantic Similarity** — Uses `sentence-transformers/all-MiniLM-L6-v2` embeddings to compute cosine similarity against industry prototypes. Handles paraphrased or indirect topic descriptions.
3. **LLM Classification** — Only triggered if keyword + semantic scores are both below threshold. Sends the topic to Claude/OpenAI/Groq for open-ended classification.

**Output:** `DetectedContext` — industry, confidence score, sub-sector, target audience, recommended theme, compliance context (e.g., HIPAA for healthcare).

**Theme auto-selection logic:**

| Audience / Industry | Auto-Selected Theme |
|---|---|
| Executive audience | `executive` |
| Technical audience | `dark_modern` |
| Finance / Insurance | `professional` |
| Default | `corporate` |

---

### Agent 2 — Design Agent

**Budget:** 20 seconds | **LLM:** 1 call (Claude/OpenAI/Groq)

**What it does:** Generates a complete visual identity for the presentation — specific to the topic and industry.

**LLM interaction:** The agent sends the topic, industry, and a menu of 10 built-in palettes to the LLM. The LLM selects the most appropriate palette and optionally refines individual colors to better match the topic's visual character.

**Output:** `DesignSpec` — a complete design contract:

| Field | Description |
|---|---|
| `primary_color` | Dominant color (60–70% visual weight) |
| `secondary_color` | Supporting color |
| `accent_color` | Sharp accent for callouts and highlights |
| `text_color` / `text_light_color` | Body and muted text |
| `background_color` | Light slide background |
| `background_dark_color` | Dark slide background (title + conclusion) |
| `chart_colors` | 5-color palette for data visualizations |
| `font_header` / `font_body` | Typography pairing (e.g., Georgia / Calibri) |
| `motif` | Visual motif across all slides (e.g., `left-bar`, `corner-accent`) |
| `palette_name` | Human-readable name for logging |

**Design principles enforced:**
- Bold, content-informed color palette — specific to this topic
- Dominance over equality: one color at 60–70% visual weight
- Dark/light contrast sandwich: dark title + conclusion slides, light content slides
- No cream/beige backgrounds; no decorative accent lines under titles

**Fallback:** If the LLM call fails, the agent selects from 4 built-in enterprise palettes based on the detected theme.

---

### Agent 3 — Storyboarding Agent

**Budget:** 10 seconds | **LLM:** Optional (narrative optimization only)

**What it does:** Plans the exact slide structure before any content is generated. This agent has **absolute authority** over slide structure — LLMs fill content into predefined structures; they do not decide structure.

**Complexity analysis:**

| Complexity | Criteria | Slide Count |
|---|---|---|
| Simple | < 10 words, no complexity signals | 7 slides |
| Moderate | 10–30 words or some domain signals | 12 slides |
| Complex | > 30 words or many domain signals | 18 slides |

**Consulting storytelling structure:**

| Section | Allocation |
|---|---|
| Title | 1 slide |
| Agenda | 1 slide |
| Problem / Context | 15% of remaining |
| Analysis | 30% of remaining |
| Evidence / Data | 25% of remaining |
| Recommendations | 20% of remaining |
| Conclusion | 10% of remaining |

**Visual diversity enforcement:** Maximum 2 consecutive slides of the same type. Slide types: `title`, `content`, `chart`, `table`, `comparison`, `metric`.

**Output:** `PresentationPlanJSON` — total slide count, sections with slide counts, slide types per section, visual diversity check flag.

**Phase 3 Enhancement:** An optional LLM call can optimize the narrative arc for executive impact, adding approximately +0.35 quality points to the final score.

---

### Agent 4 — Research Agent

**Budget:** 60 seconds | **LLM:** 1 call with 3 retries (exponential backoff)

**What it does:** Generates industry-specific research findings to ground the presentation in real domain knowledge.

**LLM interaction:** Sends topic + industry + sub-sector + target audience to the LLM. The LLM returns structured research findings.

**Output:** `ResearchFindings`:
- 6–10 research sections (each with title, key points, data points)
- 3–6 identified risks
- 3–6 identified opportunities
- 5–10 domain-specific terminology definitions
- Context summary paragraph

**Resilience:** 3 retries with exponential backoff (2s base). If all retries fail, falls back to pre-loaded cached industry data for 10 industries.

**Caching:** Results cached in Redis for 6 hours, keyed by `industry + topic_hash`. Same topic + industry combination skips the LLM call entirely on repeat requests.

---

### Agent 5 — Data Enrichment Agent

**Budget:** 20 seconds | **LLM:** None (fully deterministic)

**What it does:** Generates realistic, industry-appropriate business data for charts, tables, and KPI metrics.

**How it works:**
1. Computes `SHA-256(topic)` → deterministic seed (same topic always produces same data)
2. Uses `INDUSTRY_DATA_RANGES` — bounded realistic value ranges for 11 industries (e.g., healthcare: patient satisfaction 75–95%, bed occupancy 65–90%)
3. Generates 4 chart datasets + 1 table dataset + 10 key metrics
4. Suggests appropriate chart types based on data characteristics (pie for market share, line for trends, bar for comparisons, area for growth, scatter for correlations)

**Output:** `EnrichedData` — charts, tables, key metrics, seed value, topic hash (for audit trail).

**Caching:** Same 6-hour Redis cache as Research Agent.

---

### Agent 6 — Prompt Engineering Agent

**Budget:** 5 seconds | **LLM:** None (fully deterministic)

**What it does:** Constructs the optimal prompt for the LLM content generation step, tailored to the specific provider being used.

**Provider-specific optimization:**

| Provider | Style | Input Limit | Output Limit |
|---|---|---|---|
| Claude | Verbose, XML-structured, detailed examples | 200K tokens | 16K tokens |
| OpenAI | Concise, direct, clear JSON examples | 128K tokens | 16K tokens |
| Groq | Efficient, minimal but content-dense | 32K tokens | 16K tokens |
| Local | Simple, forgiving, basic structure | 8K tokens | 4K tokens |

**What goes into the prompt:**
- The `PresentationPlanJSON` (exact slide structure the LLM must follow)
- Research findings (domain knowledge)
- Enriched data (chart values, KPI numbers, table data)
- Design spec context (accent colors for callouts, font names)
- Strict JSON schema instructions for `Slide_JSON` output format
- Provider-specific few-shot examples

**Output:** `OptimizedPrompt` — system prompt, user prompt, prompt ID (SHA-256 hash for LangSmith tracing), version metadata.

---

### Agent 7 — LLM Provider Agent

**Budget:** 300 seconds | **LLM:** 1 call (primary + automatic failover)

**What it does:** Sends the optimized prompt to the LLM and receives the full `Slide_JSON` for all slides.

**Provider failover chain:**

```
Claude (primary)  →  OpenAI GPT-4o (fallback 1)  →  Groq Llama-3.3-70b (fallback 2)
```

**Circuit breaker logic:**
- Tracks success/failure rate over a rolling window of 20 calls per provider
- Opens when failure rate exceeds 20% (minimum 5 calls required)
- Stays open for 60 seconds, then enters HALF_OPEN state for a probe call
- Closes on successful probe

**Decision points:**
- If primary provider circuit is open → skip directly to fallback 1
- If fallback 1 circuit is open → skip to fallback 2
- If all providers fail → pipeline fails with partial result delivery

**Cost controls:**
- `MAX_LLM_CALLS_PER_REQUEST` (default: 4) — prevents runaway retries
- `COST_CEILING_USD` (default: $1.00) — hard spend cap per request

**JSON repair:** If the LLM returns truncated JSON (common with large outputs), the agent auto-closes the JSON structure before passing it downstream.

**LangSmith tracing:** Every call is traced with `execution_id`, `agent_name`, `provider`, `industry`, `prompt_id`, token counts, and cost.

---

### Agent 8 — Validation Agent

**Budget:** 5 seconds | **LLM:** None (fully deterministic)

**What it does:** Validates and auto-corrects the raw LLM output to ensure it conforms to the `Slide_JSON v1.0.0` schema.

**Validation steps:**
1. **Field migration** — handles LLM quirks (e.g., `chart` → `chart_data`, `kpi_badges` → `bullets`, `comparison_data` normalization)
2. **Schema validation** — checks required fields per slide type
3. **Auto-correction** — fills missing `slide_id`, `slide_number`, `type`, `title`, `content` fields
4. **Content truncation** — titles capped at 8 words; max 4 bullets per slide, max 8 words per bullet
5. **Enum validation** — `visual_hint` values normalized to valid enum members
6. **2 correction attempts** before accepting the best available result

---

### Agent 9 — Visual Refinement Agent

**Budget:** 90 seconds | **LLM:** Up to 3 batch calls

**What it does:** Applies visual polish to the validated slides — enhancing visual hierarchy, optimizing icon selection, and refining highlight text for maximum impact.

**Batch processing:** Groups slides into batches and makes up to 3 LLM calls to:
- Enhance visual hierarchy (heading emphasis, callout placement)
- Optimize icon selection (matching icons to slide content)
- Refine highlight text (the bold callout sentence on each slide)

---

### Agent 10 — Quality Scoring Agent

**Budget:** 10 seconds | **LLM:** None (fully deterministic)

**What it does:** Scores the final presentation across 5 dimensions and triggers a feedback loop if quality is insufficient.

**Scoring dimensions (weighted average → composite score 1–10):**

| Dimension | Weight | What's Measured |
|---|---|---|
| Content Depth | 25% | Specificity, data points, domain insights |
| Structure Coherence | 25% | Logical flow, section alignment, narrative arc |
| Visual Appeal | 20% | Design coherence, icon usage, highlight text |
| Data Accuracy | 15% | Realistic values, industry-appropriate metrics |
| Clarity | 15% | Title clarity, bullet conciseness, readability |

**Feedback loop:**
- If composite score < 8.0 AND retry count < 2 → re-run Agents 7–10
- Maximum 2 retries = 3 total generation attempts
- Each retry uses the same prompt but may hit a different LLM provider

**Output:** `QualityScoreResult` — composite score, 5 dimension scores, improvement recommendations (stored in PostgreSQL).

---

## 6. Pipeline Orchestrator — Control Plane

The `PipelineOrchestrator` is the control plane that coordinates all 10 agents. Key capabilities:

**Checkpoint recovery:** After each agent completes, its output is persisted to the `agent_states` table in PostgreSQL. If the pipeline crashes mid-run, it resumes from the last completed agent — no work is lost.

**Latency budget enforcement:** Each agent runs inside `asyncio.wait_for()` with its configured timeout. If an agent exceeds its budget, it is cancelled and the pipeline either retries or delivers partial results.

**Partial result delivery:** If the pipeline fails after Agent 7 (LLM Provider), whatever slides were generated are saved to the database and returned to the user rather than showing a blank error.

**Cancellation support:** The orchestrator polls a Redis cancellation flag between agents. If the user cancels the job, the pipeline stops cleanly at the next agent boundary.

**State cleanup:** Agent state snapshots older than 7 days are automatically purged (audit logs are preserved indefinitely).

**PipelineContext** — the mutable state object passed through the entire pipeline:

```
topic, user_selected_theme
  → detected_context    (Agent 1 — Industry Classifier)
  → design_spec         (Agent 2 — Design Agent)
  → presentation_plan   (Agent 3 — Storyboarding)
  → research_findings   (Agent 4 — Research)
  → enriched_data       (Agent 5 — Data Enrichment)
  → optimized_prompt    (Agent 6 — Prompt Engineering)
  → raw_llm_output      (Agent 7 — LLM Provider)
  → validated_slides    (Agent 8 — Validation)
  → refined_slides      (Agent 9 — Visual Refinement)
  → quality_result      (Agent 10 — Quality Scoring)
```

---

## 7. PPTX Generation — How the File is Built

### Step 1 — Export Request

The user clicks "Download PPTX". The backend enqueues an `export_pptx_task` Celery job.

### Step 2 — Python → Node.js Handoff

The Celery worker calls the `pptx-service` microservice:

```json
POST http://pptx-service:3001/build
{
  "slides": [...],
  "design_spec": { "primary_color": "...", "accent_color": "...", ... },
  "theme": "executive"
}
```

### Step 3 — Design Resolution

`pptx-service/builder.js` resolves the final color palette by merging the `DesignSpec` (LLM-generated, topic-specific colors) over the base theme palette. This ensures the PPTX colors exactly match what the user saw in the browser preview.

### Step 4 — Slide-by-Slide Rendering

Each slide is rendered by a dedicated builder function based on its type:

| Slide Type | Layout Description |
|---|---|
| **Title** | Dark background, left teal accent stripe, decorative glowing circles, large title, subtitle, up to 4 KPI badges, bottom accent bar. Special "Thank You" variant with centered layout. |
| **Content** | Dark header bar with section label + teal accent line, title, 2–4 bullet points with icon badges, highlight box (bold callout sentence), slide number. |
| **Chart** | Dark header, title, left panel with context bullets, right panel with chart (bar/line/pie/area/scatter/donut/stacked bar), highlight box below. |
| **Table** | Dark header, title, formatted table (left, alternating row colors, bold headers), context bullets (right), highlight box. |
| **Comparison** | Dark header, title, left column (heading + bullets), VS divider, right column (heading + bullets) — color-coded by theme accent. |
| **Metric** | Large KPI number (centered, accent color), metric label, trend badge (up/down arrow), 4 context bullets. |

**Supported chart types:** bar, line, pie, area, scatter, donut, stacked bar

**Supported slide transitions:** fade, slide (push), none

### Step 5 — Upload to MinIO

The PPTX buffer is uploaded to MinIO (S3-compatible object storage). A signed download URL with a 1-hour TTL is generated and returned to the frontend.

### Step 6 — Preview Generation (optional)

The `/preview` endpoint builds the PPTX, converts it to PDF via LibreOffice headless, then converts each PDF page to a JPEG image via `pdftoppm`. The images are returned as base64-encoded strings for in-browser preview.

---

## 8. Frontend — How Presentations are Rendered

### Real-Time Progressive Rendering

The frontend uses a custom `useSSEStream` hook to consume the Server-Sent Events stream. As each `slide_ready` event arrives, the slide is added to the viewer immediately — the user sees the presentation build itself in real time.

**SSE event types:**

| Event | Payload | UI Effect |
|---|---|---|
| `agent_start` | agent name | Progress bar advances, agent name shown |
| `agent_complete` | agent name, elapsed_ms | Step marked complete |
| `slide_ready` | full slide data | Slide appears in viewer |
| `quality_score` | composite + 5 dimensions | Score badge shown |
| `provider_switch` | from/to provider | Banner shown (e.g., "Switched to OpenAI") |
| `complete` | — | Viewer transitions to interactive mode |
| `error` | error type + message | Typed error display with retry option |

**Progress mapping:**

```
industry_classifier  =  8%
design               = 16%
storyboarding        = 24%
research             = 36%
data_enrichment      = 48%
prompt_engineering   = 56%
llm_provider         = 70%
validation           = 80%
visual_refinement    = 88%
quality_scoring      = 95%
complete             = 100%
```

### Interactive Slide Viewer

Once generation completes, the `ProgressiveSlideViewer` transitions to a full interactive viewer:
- Fullscreen mode
- Keyboard navigation (arrow keys)
- Speaker notes panel
- Dot navigation (click any dot to jump to that slide)
- Slide type-specific React components (`TitleSlide`, `ContentSlide`, `ChartSlide`, `TableSlide`, `ComparisonSlide`, `MetricSlide`)

### Color Consistency

The frontend resolves colors using the same `DesignSpec` that was used to build the PPTX. The `designSpecToColors(spec)` function maps the DesignSpec fields to CSS variables, ensuring the browser preview and the downloaded PPTX are visually identical.

### Additional UI Components

| Component | Purpose |
|---|---|
| `ThemeSelector` | Visual theme picker (4 themes with live preview swatches) |
| `DetectedContextBadges` | Shows auto-detected industry, audience, confidence |
| `ProviderSwitchBanner` | Notifies user when LLM provider failover occurred |
| `PresentationEditor` | Inline slide editing with `SlideEditPanel` |
| `DraggableSlideList` | Reorder slides via drag-and-drop |
| `VersionHistoryPanel` | View and restore previous versions |
| `CollaborationPanel` | Multi-user collaboration features |
| `ExportPreviewPanel` | Preview PPTX slides as images before downloading |

---

## 9. Security, Multi-Tenancy & Observability

### Security Middleware Stack (applied in order)

1. `SecurityHeadersMiddleware` — HTTPS enforcement, CSP, X-Frame-Options, HSTS
2. `APIVersioningMiddleware` — API-Version header, deprecation/sunset dates
3. `CORSMiddleware` — explicit origin whitelist
4. `SanitizationMiddleware` — input validation (topic max 5,000 chars, theme enum validation)
5. `AuditMiddleware` — logs all mutations and sensitive reads
6. `TenantMiddleware` — extracts tenant ID from JWT, scopes all queries
7. `RBACMiddleware` — role-based access control (admin / member / viewer)

### Rate Limiting

| Role | Limit | Window |
|---|---|---|
| member (free) | 10 requests | per hour |
| admin (premium) | 100 requests | per hour |

Redis sliding window. Headers returned: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

### Observability

- **LangSmith** — every LLM call traced with execution ID, agent name, provider, industry, prompt ID, token counts, cost
- **structlog** — structured JSON logging across all services
- **Health monitoring** — background task polls provider health every 30 seconds, tracks success rate and average response time per provider

---

## 10. Phase 1 Summary — What's Delivered

This initial release delivers a complete, production-ready platform with:

- ✅ One-input presentation generation (topic → full PPTX)
- ✅ 10-agent AI pipeline with checkpoint recovery and feedback loops
- ✅ 4 enterprise visual themes with LLM-driven design spec generation
- ✅ 6 slide types (title, content, chart, table, comparison, metric)
- ✅ 7 chart types (bar, line, pie, area, scatter, donut, stacked bar)
- ✅ Real-time progressive rendering via SSE
- ✅ Enterprise PPTX export via dedicated Node.js microservice
- ✅ Multi-provider LLM failover (Claude → OpenAI → Groq) with circuit breakers
- ✅ Quality scoring with automatic feedback loop (re-generates if score < 8.0)
- ✅ Multi-tenant architecture with JWT auth and RBAC
- ✅ Full LangSmith observability and cost tracking
- ✅ Inline slide editing, drag-and-drop reordering, version history

---

## 11. Future Phases — Roadmap

### Phase 2 — LLM-Driven Layout Variants

Rather than a fixed set of slide layouts, the system will use LLMs to dynamically select and compose layout variants based on the content type, data density, and narrative position of each slide. This enables a much richer visual vocabulary — for example, a data-heavy analysis slide might automatically adopt a split-panel layout with an inline chart, while a recommendation slide might use a card-grid layout. Layout decisions will be made per-slide, not per-presentation.

### Phase 3 — Theme Factories for Dynamic Presentation Styling

The current system uses 4 static base themes with LLM-driven color overrides. Phase 3 will introduce a **Theme Factory** system — a generative layer that creates entirely new, topic-specific themes on demand. Given a topic like "Sustainable Energy Transition," the Theme Factory will generate a cohesive visual system (color palette, typography, iconography style, background textures, chart color ramps) that is unique to that presentation. Themes will be versioned, shareable, and reusable across presentations.

---

---

## 12. Performance & Optimization — Why the Platform Builds Presentations Fast

Speed is a first-class design goal. The platform uses a layered set of optimizations that work together to minimize end-to-end latency. Here is every mechanism, exactly as implemented in the codebase.

---

### 12.1 Multi-Layer Caching Strategy

This is the single biggest speed lever. Three independent cache layers sit in Redis, each with a 6-hour TTL.

**Layer 1 — Final Slide_JSON Cache (biggest win)**

Before the pipeline even starts, the orchestrator checks whether the complete output already exists in Redis. The cache key is a SHA-256 hash of five components:

```
sha256( topic + industry + theme + provider_config_hash + prompt_version )
```

If a hit is found, the entire 10-agent pipeline is **skipped entirely** — the presentation is served in milliseconds. This is the most impactful optimization in the system.

Cache invalidation is automatic and precise:
- Prompt version update → all Slide_JSON keys invalidated
- Provider config change → all Slide_JSON keys invalidated
- Schema version bump → all caches (Slide_JSON + research + enrichment) invalidated

**Layer 2 — Research Cache**

Research findings are cached by `sha256(topic + industry)`. On a cache hit, Agent 4 (Research) skips its 60-second LLM call entirely. This saves the most wall-clock time of any individual agent.

**Layer 3 — Data Enrichment Cache**

Enriched data (charts, tables, KPI metrics) is cached by the same `sha256(topic + industry)` key. On a cache hit, Agent 5 (Data Enrichment) is skipped. Since data enrichment is deterministic (seed-based), the cached result is always identical to what would be regenerated.

**Combined cache hit benefit:** Research + Enrichment cache hits save approximately 60–80 seconds per request.

---

### 12.2 Deterministic Agents — No LLM Calls Where Not Needed

Five of the ten agents make **zero LLM calls**. They run in pure Python and complete in milliseconds:

| Agent | Time Budget | Why No LLM Needed |
|---|---|---|
| Storyboarding | 10s | Rule-based complexity analysis + consulting structure templates |
| Data Enrichment | 20s | SHA-256 seed → `random.Random(seed)` → bounded industry ranges |
| Prompt Engineering | 5s | Template rendering + token limit validation |
| Validation | 5s | JSON schema validation + deterministic field correction |
| Quality Scoring | 10s | Weighted formula across 5 dimensions — pure arithmetic |

**Total deterministic agent budget: 50 seconds.** In practice these agents complete in 1–5 seconds each because they do no I/O.

The Data Enrichment agent is a particularly clean example: it computes `SHA-256(topic)`, takes the first 8 hex characters as an integer seed, and feeds that into Python's `random.Random`. The same topic always produces the same data — no LLM, no network, no variance.

---

### 12.3 Proactive Cache Warming

The platform does not wait for users to request a topic before caching it. A background `CacheWarmingTask` runs every hour and:

1. Queries PostgreSQL for the top 5 most-generated topics per industry over the last 7 days
2. Checks whether each topic already has a valid Slide_JSON cache entry
3. For any cache miss, enqueues a Celery generation job to pre-populate the cache

This means popular topics are almost always served from cache with zero pipeline latency.

---

### 12.4 Provider Health Monitoring & Instant Failover

Slow LLM responses are the dominant source of latency. The platform avoids waiting for a failing provider through two mechanisms:

**Circuit Breaker (per provider):**
- Tracks success/failure rate over a rolling window of 20 calls
- Opens the circuit when failure rate exceeds 20% (minimum 5 calls)
- Stays open for 60 seconds, then probes with a single call (HALF_OPEN)
- If the primary provider's circuit is open, the pipeline skips it immediately and goes straight to the fallback — no timeout wait

**Health Monitor Background Task:**
- Runs every 30 seconds, updating Redis with current health metrics for all providers
- Runs every 5 minutes to persist metrics to PostgreSQL
- Automatically restores the primary provider when its success rate recovers
- The `select_provider()` function uses these cached health metrics to pick the best available provider before each call — no cold-start penalty

**Failover chain:** Claude → OpenAI GPT-4o → Groq Llama-3.3-70b. Switching providers takes milliseconds because the circuit breaker decision is made from in-memory state.

---

### 12.5 Per-Agent Latency Budgets with Hard Timeouts

Every agent runs inside `asyncio.wait_for()` with a hard timeout. If an agent exceeds its budget, it is cancelled immediately — the pipeline does not hang waiting for a slow response.

| Agent | Budget | Rationale |
|---|---|---|
| Industry Classifier | 15s | Keyword + embedding; LLM only as last resort |
| Design Agent | 20s | Single LLM call for palette selection |
| Storyboarding | 10s | Deterministic; budget is a safety net |
| Research | 60s | LLM call with 3 retries; complex topics need time |
| Data Enrichment | 20s | Deterministic; budget is a safety net |
| Prompt Engineering | 5s | Template rendering only |
| LLM Provider | 300s | Full presentation generation; large output |
| Validation | 5s | Deterministic JSON correction |
| Visual Refinement | 90s | Up to 3 batch LLM calls |
| Quality Scoring | 10s | Deterministic formula |
| **Total pipeline budget** | **570s** | Hard ceiling; partial results delivered on breach |

The total pipeline budget is 570 seconds, but typical runs complete in 60–120 seconds because most agents finish well under their budgets and the Research + Enrichment agents are often served from cache.

---

### 12.6 Checkpoint Recovery — No Wasted Work on Failure

If the pipeline crashes mid-run (network blip, container restart, provider timeout), it does not start over. After every agent completes, the orchestrator:

1. Persists the agent's output to the `agent_states` table in PostgreSQL (JSONB)
2. Persists the full `PipelineContext` as a `_checkpoint` record

On the next attempt, the orchestrator loads the checkpoint and skips every agent that already has a completed state. This means a failure at Agent 8 (Validation) only re-runs Agents 8–10 — not the expensive Research and LLM Provider agents.

---

### 12.7 Async I/O Throughout — No Blocking

The entire backend is built on Python's `asyncio`. Every database query, Redis operation, LLM call, and HTTP request is non-blocking:

- **FastAPI** with `async def` route handlers
- **SQLAlchemy 2** with `AsyncSession` — all DB queries use `await db.execute()`
- **redis.asyncio** — all cache reads/writes are awaited
- **LangChain** `ainvoke()` — all LLM calls are async
- **Celery** worker runs the pipeline in an async event loop via `asyncio.run()`

This means the Celery worker can handle multiple concurrent pipeline executions without threads blocking each other on I/O.

---

### 12.8 Research Agent — Exponential Backoff, Not Blind Retry

The Research Agent (the most latency-sensitive LLM call) implements a precise retry strategy:

```
Attempt 1: 30s timeout
  → fail → wait 2s
Attempt 2: 30s timeout
  → fail → wait 4s
Attempt 3: 30s timeout
  → fail → use cached industry data (instant)
```

The exponential backoff (2s base, doubling each retry) prevents hammering a struggling provider. The cached industry fallback ensures the pipeline always completes — even if all LLM retries fail — with zero additional latency.

---

### 12.9 Partial Result Delivery — Never a Blank Screen

If the pipeline fails after Agent 7 (LLM Provider), whatever slides were generated are saved to PostgreSQL and returned to the user. The user sees a partial presentation rather than an error page. This is implemented in `_persist_partial_result()` in the orchestrator.

This also means the perceived latency is lower — the user starts seeing slides via SSE as soon as Agent 8 (Validation) completes, even before quality scoring finishes.

---

### 12.10 Real-Time Progressive Rendering via SSE

The frontend does not wait for the full pipeline to complete before showing results. Server-Sent Events stream slide data to the browser as each agent finishes:

- `agent_start` / `agent_complete` events update the progress bar in real time
- `slide_ready` events are published immediately after Agent 8 (Validation) — one event per slide
- The user sees slides appearing one by one while Visual Refinement and Quality Scoring are still running

This makes the perceived generation time significantly shorter than the actual pipeline duration.

---

### 12.11 Lazy Agent Loading — Fast Startup

The `PipelineOrchestrator` uses lazy imports for all agent modules:

```python
def _load_agents(self) -> None:
    if self._agents_loaded:
        return
    from app.agents.industry_classifier import industry_classifier
    from app.agents.design_agent import design_agent
    # ... etc
    self._agents_loaded = True
```

Agents are only imported on the first pipeline run, not at module load time. This avoids circular import issues and keeps the Celery worker startup time fast.

---

### 12.12 Idempotency Keys — No Duplicate Work

Every Celery task is protected by an idempotency key:
- Generation: `gen:{presentation_id}`
- Export: `export:{presentation_id}:{timestamp}`

If the same task is enqueued twice (e.g., due to a network retry), the second enqueue is a no-op. This prevents duplicate LLM calls and duplicate PPTX exports.

---

### 12.13 Provider-Specific Token Limits — Right-Sized Outputs

The Prompt Engineering agent tailors the prompt to the active provider's token limits. This prevents over-generating (wasting tokens and time) and under-generating (truncated output that requires a retry):

| Provider | Max Output Tokens | Strategy |
|---|---|---|
| Claude | 32,000 | Verbose, XML-structured prompts; full detail |
| OpenAI | 16,000 | Concise, direct prompts |
| Groq | 16,000 | Minimal but content-dense prompts |
| Local | 4,096 | Simple, forgiving prompts |

Right-sizing the output means the LLM finishes faster and the JSON repair step (auto-closing truncated JSON) is rarely needed.

---

### 12.14 Slide_JSON Cache Analytics

The platform tracks cache performance in real time so the team can measure the impact of caching:

| Metric | How It's Tracked |
|---|---|
| Cache hit rate | `hits / (hits + misses)` — Redis counter |
| Cost saved | `hits × $0.05` (estimated cost per generation) |
| Storage used | Byte count of all cached JSON — Redis counter |
| Reset cadence | Every 24 hours |

These analytics are available via the admin API and help quantify exactly how much time and money the caching layer is saving per day.

---

### Performance Summary

| Optimization | Time Saved | Mechanism |
|---|---|---|
| Slide_JSON cache hit | Full pipeline (~60–120s) | SHA-256 composite key in Redis |
| Research cache hit | ~60s | topic+industry key in Redis |
| Enrichment cache hit | ~5–10s | topic+industry key in Redis |
| Deterministic agents | ~50s budget, ~5–15s actual | No LLM calls in 5 of 10 agents |
| Circuit breaker failover | Avoids 30–60s timeout wait | In-memory failure rate tracking |
| Async I/O | Eliminates thread blocking | asyncio throughout the stack |
| Checkpoint recovery | Skips completed agents on retry | PostgreSQL agent_states table |
| Progressive SSE rendering | Perceived latency ~50% lower | slide_ready events after validation |
| Cache warming | Popular topics always cached | Hourly background Celery task |
| Exponential backoff | Avoids cascading retries | 2s base, doubles per attempt |

---

*Document prepared for client demo — AI Presentation Intelligence Platform, Phase 1*
