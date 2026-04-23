# Architecture & Agent Pipeline — AI Presentation Intelligence Platform

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER BROWSER                                       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    React Frontend (Port 5173)                         │   │
│  │                                                                       │   │
│  │  PresentationGenerator → ThemeSelector → PresentationWorkflow        │   │
│  │       (topic input)      (theme picker)    (SSE + SlideViewer)       │   │
│  └──────────────────────────────┬────────────────────────────────────────┘  │
└─────────────────────────────────┼───────────────────────────────────────────┘
                                  │  HTTP REST + SSE
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend (Port 8000)                           │
│                                                                              │
│  ┌──────────┐ ┌──────┐ ┌──────────┐ ┌───────────┐ ┌────────────────────┐  │
│  │ Security │ │ CORS │ │  Audit   │ │  Tenant   │ │  RBAC Middleware   │  │
│  │ Headers  │ │      │ │ Logging  │ │ Isolation │ │  (admin/member/    │  │
│  │          │ │      │ │          │ │           │ │   viewer)          │  │
│  └────┬─────┘ └──┬───┘ └────┬────┘ └─────┬─────┘ └──────────┬─────────┘  │
│       └──────────┴──────────┴─────────────┴──────────────────┘             │
│                               ▼                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         API Router                                      │ │
│  │  POST /presentations          → Enqueue Celery Task (+ optional theme) │ │
│  │  GET  /presentations/{id}/stream → Redis Stream → SSE                  │ │
│  │  GET  /presentations/{id}/status → DB Poll                             │ │
│  │  GET  /presentations/{id}        → Full Slide_JSON                     │ │
│  │  POST /presentations/{id}/export → Enqueue PPTX Export                 │ │
│  │  DELETE /jobs/{job_id}           → Cancel running job                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │  Celery Task
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Celery Worker (Background)                              │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                  Pipeline Orchestrator                               │    │
│  │                                                                      │    │
│  │  ① Industry      ② Design        ③ Storyboarding  ④ Research       │    │
│  │    Classifier  →    Agent      →    Agent       →    Agent       →  │    │
│  │                                                                      │    │
│  │  ⑤ Data          ⑥ Prompt        ⑦ LLM Provider  ⑧ Validation      │    │
│  │    Enrichment  →    Engineering →    Agent       →    Agent       →  │    │
│  │                                                                      │    │
│  │  ⑨ Visual        ⑩ Quality                                          │    │
│  │    Refinement  →    Scoring                                          │    │
│  │                                                                      │    │
│  │  [Feedback Loop: if score < 8.0, re-run ⑦→⑩ up to 2 times]        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  PPTX Export Task → calls pptx-service → uploads to MinIO → signed URL     │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                         ▼
┌──────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│  PostgreSQL 16   │   │      Redis 7          │   │    MinIO (S3)        │
│                  │   │                       │   │                      │
│  - presentations │   │  - Celery broker      │   │  - PPTX exports      │
│  - users/tenants │   │  - Result backend     │   │  - Signed URLs       │
│  - agent_states  │   │  - Redis Streams      │   │    (1hr TTL)         │
│  - quality_scores│   │    (SSE events)       │   │                      │
│  - templates     │   │  - Cache (research,   │   │                      │
│  - audit_logs    │   │    enrichment, slides)│   │                      │
│  - design_spec   │   │  - Rate limit counters│   │                      │
└──────────────────┘   └──────────────────────┘   └──────────────────────┘
          │                                                │
          ▼                                                ▼
┌──────────────────────────────┐   ┌───────────────────────────────────────┐
│       LLM Providers          │   │     pptx-service (Port 3001)          │
│                              │   │                                       │
│  Primary: Anthropic Claude   │   │  Node.js + Express + pptxgenjs       │
│  Fallback 1: OpenAI GPT-4o  │   │  POST /build  → PPTX buffer          │
│  Fallback 2: Groq Llama-3.3 │   │  POST /preview → slide images        │
│                              │   │                                       │
│  Circuit breaker + backoff   │   │  4 theme palettes built-in           │
│  LangSmith tracing           │   │  DesignSpec override support          │
└──────────────────────────────┘   └───────────────────────────────────────┘
```

---

## 2. Request Lifecycle

```
User submits topic "Healthcare sector market analysis" (optional: theme="corporate")
         │
         ▼
POST /api/v1/presentations { topic, theme? }
  → Create Presentation record (status=queued)
  → Create PipelineExecution record
  → Enqueue generate_presentation Celery task (with user_selected_theme)
  → Return { job_id, presentation_id }
         │
         ▼
Frontend connects to SSE stream
GET /api/v1/presentations/{id}/stream?token=<jwt>
  → Reads from Redis Stream (stream:presentation:{id})
  → Yields SSE events as they arrive
         │
         ▼
Celery Worker picks up task
  → Runs 10-agent pipeline sequentially
  → Each agent publishes events to Redis Stream
  → Frontend receives events in real-time
  → User-selected theme overrides auto-detected theme (if provided)
         │
         ▼
Pipeline completes
  → Presentation + design_spec saved to PostgreSQL
  → Cache Slide_JSON in Redis (6hr TTL)
  → "complete" SSE event sent
  → Frontend transitions to completed state
         │
         ▼
User clicks "Download PPTX"
POST /api/v1/presentations/{id}/export
  → Enqueue export_pptx Celery task
  → Task calls pptx-service with slides + design_spec + theme
  → pptx-service builds PPTX via pptxgenjs
  → Upload to MinIO, return signed download URL (1hr TTL)
```

---

## 3. SSE Event Flow

```
Redis Stream: stream:presentation:{id}
                    │
    ┌───────────────┼───────────────────────────────────────┐
    │               │                                       │
    ▼               ▼                                       ▼
agent_start    agent_complete                          slide_ready
{              {                                       {
  agent:          agent: "industry_classifier",          slide_number: 4,
  "industry_      elapsed_ms: 2440.7                     total_slides: 12,
  classifier"   }                                        slide: { ...full slide data }
}                                                      }
    │
    ▼
quality_score                    complete                  error
{                                {                         {
  composite_score: 8.01,           execution_id: "...",     error: "...",
  dimensions: {                    quality_score: 8.01      failed_agent: "..."
    content_depth: 9.5,          }                         }
    visual_appeal: 5.5,
    ...
  }
}
```

---

## 4. Multi-Agent Pipeline — Detailed

```
Topic Input (+ optional user_selected_theme)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 1: Industry Classifier                          Latency budget: 15s  │
│                                                                              │
│  Input:  topic string                                                        │
│  Output: DetectedContext {                                                   │
│    industry, confidence, sub_sector,                                         │
│    target_audience, template_name, theme                                     │
│  }                                                                           │
│                                                                              │
│  3-step classification:                                                      │
│  Step 1 → Keyword matching (10+ industry seed term sets)                    │
│  Step 2 → Semantic similarity (sentence-transformers all-MiniLM-L6-v2)      │
│  Step 3 → LLM classification (open-ended, handles any industry)             │
│                                                                              │
│  Theme selection (overridden if user chose a theme):                        │
│    executives → executive, technical → dark_modern,                          │
│    finance/insurance analysts → professional, default → corporate            │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 2: Design Agent                                 Latency budget: 20s  │
│                                                                              │
│  Input:  topic, industry, theme                                              │
│  Output: DesignSpec {                                                        │
│    primary_color, secondary_color, accent_color,                             │
│    text_color, text_light_color, background_color, background_dark_color,   │
│    chart_colors[5], font_header, font_body, motif, palette_name             │
│  }                                                                           │
│                                                                              │
│  LLM call to generate topic-specific palette from 10 available palettes     │
│  Industry-specific palette hints (e.g. healthcare → teal/navy, avoid red)   │
│  5 visual motifs: left-bar, corner-accent, icon-circle, stat-callout,       │
│    glow-dot                                                                  │
│  5 font pairings: Georgia/Calibri, Arial Black/Arial, Calibri/Calibri Light│
│  Fallback palettes per theme when LLM is unavailable                        │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 3: Storyboarding                                Latency budget: 10s  │
│                                                                              │
│  Input:  topic, industry, template_structure                                 │
│  Output: PresentationPlanJSON {                                              │
│    total_slides (5-25), sections: [                                          │
│      { name, slide_count, slide_types[] }                                    │
│    ]                                                                         │
│  }                                                                           │
│                                                                              │
│  Deterministic — NO LLM call (pure logic)                                   │
│  Complexity analysis: simple(7) / moderate(12) / complex(18) slides         │
│  Visual diversity enforcement: max 2 consecutive slides of same type        │
│  Has ABSOLUTE AUTHORITY over slide structure — LLM fills content only       │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 4: Research                                     Latency budget: 60s  │
│                                                                              │
│  Input:  topic, industry, sub_sector, target_audience                        │
│  Output: ResearchFindings {                                                  │
│    sections[6-10], risks[3-6], opportunities[3-6],                           │
│    terminology[5-10], context_summary                                        │
│  }                                                                           │
│                                                                              │
│  LLM call with 60s timeout, 3 retries (exponential backoff)                │
│  Fallback: cached industry data (10 industries pre-loaded)                  │
│  Results cached in Redis for 6 hours (same topic = instant)                 │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 5: Data Enrichment                              Latency budget: 20s  │
│                                                                              │
│  Input:  topic, industry, research_findings                                  │
│  Output: EnrichedData {                                                      │
│    charts[4], tables[1], key_metrics{10}, seed, topic_hash                  │
│  }                                                                           │
│                                                                              │
│  Seed-based generation: SHA-256(topic) → deterministic seed                 │
│  Industry-specific labels and realistic value ranges                        │
│  Chart type suggestion: pie(composition), line(trends), bar(comparison)     │
│  Results cached in Redis for 6 hours                                        │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 6: Prompt Engineering                            Latency budget: 5s  │
│                                                                              │
│  Input:  topic, industry, research, plan, enrichment, provider_type         │
│  Output: OptimizedPrompt { system_prompt, user_prompt, prompt_id, version } │
│                                                                              │
│  Deterministic — NO LLM call (pure template rendering)                      │
│  Provider-specific templates: Claude (XML), OpenAI (concise), Groq (minimal)│
│  Token limit validation per provider                                        │
│  Prompt versioning with SHA-256 prompt_id for LangSmith tracing            │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 7: LLM Provider                               Latency budget: 300s  │
│                                                                              │
│  Input:  system_prompt, user_prompt                                          │
│  Output: raw Slide_JSON (12-18 slides with full content)                    │
│                                                                              │
│  Provider failover chain: Claude → OpenAI → Groq                           │
│  Circuit breaker: opens when failure rate > 20% (min 5 calls)              │
│  JSON repair: auto-closes truncated JSON                                    │
│  LangSmith tracing: every call traced with execution_id metadata           │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 8: Validation                                    Latency budget: 5s  │
│                                                                              │
│  Input:  raw Slide_JSON from LLM                                             │
│  Output: validated + corrected Slide_JSON                                   │
│                                                                              │
│  Deterministic — NO LLM call                                                │
│  Field migrations: slide["chart"] → content["chart_data"], etc.             │
│  Auto-corrections: missing IDs, type mapping, visual_hint inference         │
│  Content constraints: title ≤8 words, ≤4 bullets, ≤8 words per bullet      │
│  2 correction attempts before accepting result                              │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 9: Visual Refinement                            Latency budget: 90s  │
│                                                                              │
│  Post-validation visual polish pass                                          │
│  Batch processing with up to 3 LLM calls                                   │
│  Enhances visual hierarchy, icon selection, highlight text                  │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 10: Quality Scoring                             Latency budget: 10s  │
│                                                                              │
│  Input:  validated slides[]                                                  │
│  Output: QualityScoreResult {                                                │
│    composite_score (1-10), 5 dimension scores, recommendations              │
│  }                                                                           │
│                                                                              │
│  Deterministic — NO LLM call                                                │
│  5 Dimensions (weighted average):                                            │
│    Content Depth (25%) · Visual Appeal (20%) · Structure Coherence (25%)    │
│    Data Accuracy (15%) · Clarity (15%)                                      │
│                                                                              │
│  Feedback loop: if composite < 8.0 AND retries < 2                         │
│    → Re-run from Agent 7 (LLM Provider) through Agent 10                   │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
Pipeline Finalized
  → Save slides + design_spec to PostgreSQL
  → Cache Slide_JSON in Redis (6hr TTL)
  → Publish "complete" event to Redis Stream
  → Increment template usage counter
```

---

## 5. Data Flow Example

```
Topic: "Healthcare sector market analysis"
User theme: (none — auto-detect)
         │
         ▼ Agent 1 (Industry Classifier)
industry="healthcare", theme="corporate", audience="general",
template="Healthcare Executive Briefing"
         │
         ▼ Agent 2 (Design Agent)
DesignSpec: palette="Teal Trust", primary=028090, accent=02C39A,
font_header="Calibri", motif="left-bar"
         │
         ▼ Agent 3 (Storyboarding)
total_slides=12, sections=[
  Title(1), Agenda(1), Problem(2), Analysis(3),
  Evidence(2), Recommendations(2), Conclusion(1)
]
         │
         ▼ Agent 4 (Research)
sections=["Clinical Overview", "Patient Impact", ...],
risks=["Regulatory compliance", "Cybersecurity threats", ...],
opportunities=["Digital health innovation", "Cost reduction", ...]
         │
         ▼ Agent 5 (Data Enrichment)
charts=[
  { type:"bar", labels:["Primary Care","Specialty",...], data:[89,74,...] },
  { type:"line", labels:["Q1 2022","Q2 2022",...], data:[75,78,...] },
],
key_metrics={ patient_satisfaction:87.3, readmission_rate:8.2, ... }
         │
         ▼ Agent 6 (Prompt Engineering)
system_prompt="You are a senior strategy consultant..."
user_prompt="<topic>Healthcare...</topic><design_spec>...</design_spec>
<data_enrichment>KEY METRICS: Patient Satisfaction: 87.3 ..."
         │
         ▼ Agent 7 (LLM Provider — Claude)
raw JSON: { "slides": [ { "slide_type":"title", ... }, ... ] }
         │
         ▼ Agent 8 (Validation)
Corrected: type mappings, chart_data migration, visual_hint assignment
         │
         ▼ Agent 9 (Visual Refinement)
Enhanced: icon selection, highlight text, visual hierarchy
         │
         ▼ Agent 10 (Quality Scoring)
composite_score=8.01 → no feedback loop needed
```

---

## 6. Theme System

```
User selects theme in UI (ThemeSelector component)
  OR system auto-detects via Industry Classifier
         │
         ▼
Theme flows through pipeline:
  PipelineContext.user_selected_theme (overrides auto-detect)
  → detected_context["theme"]
  → DesignAgent uses theme as base palette
  → pptx-service applies theme colors to PPTX
  → Frontend resolves colors via designSpecToColors() or getThemeColors()

4 Built-in Themes:
  corporate:    #002855 navy / #005288 / #0078AC steel — enterprise default
  executive:    #003366 navy / #0066CC / #FF6600 gold — boardroom
  professional: #86BC25 green / #0076A8 / #00A3E0 teal — professional services
  dark-modern:  #6C63FF purple / #FF6584 / #43E97B green — tech-forward

DesignAgent refines palette per topic:
  10 available palettes (Midnight Executive, Forest & Moss, Coral Energy, ...)
  5 visual motifs (left-bar, corner-accent, icon-circle, stat-callout, glow-dot)
  5 font pairings (Georgia/Calibri, Arial Black/Arial, ...)
  Industry-specific hints (healthcare → teal/navy, finance → navy/gold, ...)
```

---

## 7. Frontend Rendering Pipeline

```
SSE "slide_ready" event received
         │
         ▼
ProgressiveSlideViewer.parseSlide()
  → Resolve type: slide_type > type > visual_hint inference
  → Migrate chart/table/comparison data into flat structure
  → Deduplicate by slide_number (feedback loop sends slides twice)
         │
         ▼
SlideRenderer (type dispatcher)
  ├── type="title"      → TitleSlide      (accent bar, decorative circles, footer)
  ├── type="content"    → ContentSlide    (numbered bullets, icon, highlight panel)
  ├── type="chart"      → ChartSlide      (stats panel + Recharts bar/line/area/pie)
  ├── type="table"      → TableSlide      (colored header, alternating rows, insight panel)
  ├── type="comparison" → ComparisonSlide (A vs B columns, VS divider, bottom highlight)
  └── type="metric"     → MetricSlide     (animated counter, trend badge, context bullets)
         │
         ▼
Color resolution:
  DesignSpec available? → designSpecToColors(spec) — matches PPTX export
  No DesignSpec?        → getThemeColors(theme)    — static fallback
```

---

## 8. PPTX Export Architecture

```
User clicks "Download PPTX"
         │
         ▼
POST /api/v1/presentations/{id}/export
  → Enqueue export_pptx Celery task
         │
         ▼
Celery Worker:
  → Load slides + theme + design_spec from PostgreSQL
  → POST to pptx-service:3001/build { slides, design_spec, theme }
         │
         ▼
pptx-service (Node.js):
  → resolveDesign(designSpec, theme) — merge DesignSpec with base theme
  → Build slides via pptxgenjs:
      Title: accent stripe, decorative circles, KPI badges
      Content: numbered bullet cards, icon circles, highlight bar
      Chart: bar/line/pie/area/donut via pptxgenjs chart API
      Table: colored header, alternating rows, insight panel
      Comparison: two-column cards with VS divider
      Metric: large KPI card, trend badge, context bullets
  → Return PPTX buffer
         │
         ▼
Celery Worker:
  → Upload to MinIO (S3)
  → Generate signed URL (1hr TTL)
  → Return download URL to frontend
```

---

## 9. Provider Failover Architecture

```
LLM call requested
         │
         ▼
Health Monitor checks provider health
  → success_rate, avg_response_time, circuit_open
         │
         ▼
Select best available provider
  ┌──────────────────────────────────────────────────────┐
  │  Primary: Claude (if success_rate > 0 and not open)  │
  │  Fallback 1: OpenAI (if available)                   │
  │  Fallback 2: Groq (rate-limited, exponential backoff)│
  └──────────────────────────────────────────────────────┘
         │
         ▼
Circuit Breaker Logic
  failure_rate > 20% AND calls >= 5 → OPEN circuit
  OPEN for 60s → HALF-OPEN (probe)
  Probe succeeds → CLOSED
  Probe fails → OPEN again
         │
         ▼
If all providers fail → raise "All LLM providers failed"
  → Partial results saved, status=failed
  → User can retry via POST /presentations/{id}/regenerate
```

---

## 10. Database Schema (Key Tables)

```
presentations
  presentation_id  UUID PK
  user_id          UUID FK → users
  tenant_id        UUID FK → tenants
  topic            TEXT (max 5000 chars)
  status           ENUM(queued, processing, completed, failed, cancelled)
  slides           JSONB          ← full slide array
  design_spec      JSONB          ← DesignAgent output (colors, fonts, motif)
  total_slides     INT
  selected_theme   TEXT           ← corporate | executive | professional | dark-modern
  detected_industry TEXT
  detection_confidence FLOAT
  detected_sub_sector TEXT
  inferred_audience TEXT
  quality_score    FLOAT
  schema_version   TEXT (default "1.0.0")
  created_at       TIMESTAMP
  updated_at       TIMESTAMP

pipeline_executions
  id               UUID PK
  presentation_id  UUID FK → presentations
  status           TEXT
  current_agent    TEXT
  error_message    TEXT
  prompt_id        TEXT           ← SHA-256 for LangSmith tracing
  started_at       TIMESTAMP
  completed_at     TIMESTAMP

agent_states
  id               UUID PK
  execution_id     UUID FK → pipeline_executions
  agent_name       TEXT
  state            JSONB          ← agent output snapshot (checkpoint)
  created_at       TIMESTAMP

quality_scores
  id               UUID PK
  presentation_id  UUID FK
  execution_id     UUID FK
  content_depth    FLOAT
  visual_appeal    FLOAT
  structure_coherence FLOAT
  data_accuracy    FLOAT
  clarity          FLOAT
  composite_score  FLOAT
  recommendations  JSONB

users
  id               UUID PK
  tenant_id        UUID FK → tenants
  email            TEXT UNIQUE
  hashed_password  TEXT
  role             TEXT (admin | member | viewer)

templates
  id               UUID PK
  tenant_id        UUID FK
  name             TEXT
  industry         TEXT
  slide_structure  JSONB
  usage_count      INT
  is_system        BOOLEAN

audit_logs
  id               UUID PK
  tenant_id        UUID FK
  user_id          UUID FK
  action           TEXT
  resource_type    TEXT
  resource_id      UUID
  metadata         JSONB
```

---

## 11. Middleware Stack

Requests pass through middleware in this order:

```
SecurityHeadersMiddleware  → HTTPS, CSP, X-Frame-Options, HSTS
APIVersioningMiddleware    → API-Version header, deprecation/sunset dates
CORSMiddleware             → Explicit whitelist from CORS_ORIGINS
SanitizationMiddleware     → Input validation and sanitization
AuditMiddleware            → Logs all mutations and sensitive reads
TenantMiddleware           → Sets request.state.tenant_id from JWT
RBACMiddleware             → Role-based access control (admin/member/viewer)
```

---

## 12. Checkpoint & Recovery

Each agent persists its output to `agent_states` before the next agent starts. If the pipeline crashes mid-way:

```
Resume from checkpoint:
  1. Load latest PipelineExecution for presentation_id
  2. Load all AgentState records for execution_id
  3. Reconstruct PipelineContext from saved states (including user_selected_theme)
  4. Skip already-completed agents
  5. Resume from the first incomplete agent

Partial result delivery (on failure):
  → Best available slides saved to presentations.slides
  → Status set to "failed" (not lost)
  → User can retry via POST /presentations/{id}/regenerate
```

---

## 13. Caching Strategy

```
Redis Cache Keys:
  research:{industry}:{topic_hash}       TTL: 6 hours
  enrichment:{industry}:{topic_hash}     TTL: 6 hours
  slide_json:{composite_key_sha256}      TTL: 6 hours
    (key = topic + industry + theme + provider_hash + prompt_version)
  health:{provider}                      TTL: 30 seconds
  ratelimit:{user_id}                    TTL: 1 hour (sliding window)

Cache hit → skip agent entirely (research + enrichment = ~30s saved)
Cache miss → run agent, store result
Same topic + industry + theme = identical deterministic output (seed-based)

Cache warming: background task pre-warms popular topic/industry combinations
```
