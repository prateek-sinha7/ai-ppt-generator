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
│  │  PresentationGenerator  →  PresentationWorkflow  →  SlideViewer      │   │
│  │         (input)              (SSE listener)         (renderer)        │   │
│  └──────────────────────────────┬────────────────────────────────────────┘  │
└─────────────────────────────────┼───────────────────────────────────────────┘
                                  │  HTTP REST + SSE
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend (Port 8000)                           │
│                                                                              │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │  Auth Middleware │  │  RBAC Middleware  │  │  Rate Limit Middleware   │   │
│  └────────┬────────┘  └────────┬─────────┘  └────────────┬─────────────┘   │
│           └───────────────────┬┘                          │                 │
│                               ▼                           │                 │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         API Router                                      │ │
│  │  POST /presentations  →  Enqueue Celery Task                           │ │
│  │  GET  /presentations/{id}/stream  →  Redis Stream → SSE                │ │
│  │  GET  /presentations/{id}/status  →  DB Poll                           │ │
│  │  GET  /presentations/{id}         →  Full Slide_JSON                   │ │
│  │  POST /presentations/{id}/export  →  Enqueue PPTX Export               │ │
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
│  │  ① Industry      ② Storyboarding  ③ Research    ④ Data              │    │
│  │    Classifier  →    Agent       →    Agent    →    Enrichment    →  │    │
│  │                                                                      │    │
│  │  ⑤ Prompt        ⑥ LLM Provider  ⑦ Validation  ⑧ Quality           │    │
│  │    Engineering →    Agent       →    Agent    →    Scoring          │    │
│  │                                                                      │    │
│  │  [Feedback Loop: if score < 8.0, re-run ⑥→⑦→⑧ up to 2 times]      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                         ▼
┌──────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│  PostgreSQL 16   │   │      Redis 7          │   │    MinIO (S3)        │
│                  │   │                       │   │                      │
│  - presentations │   │  - Celery broker      │   │  - PPTX exports      │
│  - users         │   │  - Result backend     │   │  - Signed URLs       │
│  - agent_states  │   │  - Redis Streams      │   │                      │
│  - quality_scores│   │    (SSE events)       │   │                      │
│  - templates     │   │  - Cache (research,   │   │                      │
│                  │   │    enrichment data)   │   │                      │
└──────────────────┘   └──────────────────────┘   └──────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         LLM Providers                                     │
│                                                                           │
│  Primary: Anthropic Claude (claude-sonnet-4-6, max 16k output tokens)    │
│  Fallback 1: OpenAI GPT-4o                                               │
│  Fallback 2: Groq Llama-3.3-70b-versatile                                │
│                                                                           │
│  Automatic failover with circuit breaker + exponential backoff           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Request Lifecycle

```
User submits topic "Healthcare sector market analysis"
         │
         ▼
POST /api/v1/presentations
  → Create Presentation record (status=queued)
  → Create PipelineExecution record
  → Enqueue generate_presentation Celery task
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
  → Runs 8-agent pipeline sequentially
  → Each agent publishes events to Redis Stream
  → Frontend receives events in real-time
         │
         ▼
Pipeline completes
  → Presentation saved to PostgreSQL
  → "complete" SSE event sent
  → Frontend transitions to completed state
         │
         ▼
User clicks "Download PPTX"
POST /api/v1/presentations/{id}/export
  → Enqueue export_pptx Celery task
  → Task builds PPTX, uploads to MinIO
  → Returns signed download URL (1hr TTL)
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
Topic Input
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
│  Step 1 → Keyword matching (10 industry seed term sets)                      │
│  Step 2 → Semantic similarity (sentence-transformers all-MiniLM-L6-v2)      │
│  Step 3 → LLM classification (open-ended, handles any industry)             │
│                                                                              │
│  Template selection matrix: maps industry + topic keywords → template name  │
│  Theme selection: executives→mckinsey, technical→dark_modern, else→deloitte │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 2: Storyboarding                                Latency budget: 10s  │
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
│  Section allocation: Title(1) + Agenda(1) + Problem + Analysis +            │
│                      Evidence + Recommendations + Conclusion                 │
│  Visual diversity enforcement: max 2 consecutive slides of same type        │
│  Has ABSOLUTE AUTHORITY over slide structure — LLM fills content only       │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 3: Research                                     Latency budget: 30s  │
│                                                                              │
│  Input:  topic, industry, sub_sector, target_audience                        │
│  Output: ResearchFindings {                                                  │
│    sections[6-10], risks[3-6], opportunities[3-6],                           │
│    terminology[5-10], context_summary                                        │
│  }                                                                           │
│                                                                              │
│  LLM call with 30s timeout, 3 retries (2s exponential backoff)              │
│  Fallback: cached industry data (10 industries pre-loaded)                  │
│  Results cached in Redis for 6 hours (same topic = instant)                 │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 4: Data Enrichment                              Latency budget: 20s  │
│                                                                              │
│  Input:  topic, industry, research_findings                                  │
│  Output: EnrichedData {                                                      │
│    charts[4]: { chart_type, title, labels[], datasets[] },                   │
│    tables[1]: { headers[], rows[][] },                                       │
│    key_metrics{10}: { metric_name: float },                                  │
│    seed, topic_hash (for reproducibility)                                    │
│  }                                                                           │
│                                                                              │
│  Seed-based generation: SHA-256(topic) → deterministic seed                 │
│  Known industries: pre-defined realistic value ranges (10 industries)       │
│  Unknown industries: LLM generates data ranges dynamically                  │
│  Industry-specific labels: "Primary Care", "Q1 2023", "North America"       │
│  Chart type suggestion: pie(composition), line(trends), bar(comparison)     │
│  Data consistency validation: NaN/Inf checks, percentage bounds             │
│  Results cached in Redis for 6 hours                                        │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 5: Prompt Engineering                            Latency budget: 5s  │
│                                                                              │
│  Input:  topic, industry, research_findings, presentation_plan,             │
│          data_enrichment, provider_type                                      │
│  Output: OptimizedPrompt {                                                   │
│    system_prompt, user_prompt,                                               │
│    estimated_tokens, prompt_id, version                                      │
│  }                                                                           │
│                                                                              │
│  Deterministic — NO LLM call (pure template rendering)                      │
│  Provider-specific templates: Claude (XML), OpenAI (concise), Groq (minimal)│
│  Token limit validation per provider (Claude: 200k, OpenAI: 128k, Groq: 32k)│
│  Auto-truncation: data_enrichment truncated first if over limit             │
│  Formats enrichment data as ready-to-copy chart_data arrays for LLM        │
│  Prompt versioning with SHA-256 prompt_id for LangSmith tracing            │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 6: LLM Provider                               Latency budget: 150s  │
│                                                                              │
│  Input:  system_prompt, user_prompt                                          │
│  Output: raw Slide_JSON (12-18 slides with full content)                    │
│                                                                              │
│  Provider failover chain: Claude → OpenAI → Groq                           │
│  Circuit breaker: opens when failure rate > 20% (min 5 calls)              │
│  Health monitoring: tracks success rate, avg response time per provider     │
│  max_tokens: Claude=16000, OpenAI=16000, Groq=8000                         │
│  JSON repair: auto-closes truncated JSON (counts unclosed { and [)         │
│  LangSmith tracing: every call traced with execution_id metadata           │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 7: Validation                                    Latency budget: 5s  │
│                                                                              │
│  Input:  raw Slide_JSON from LLM                                             │
│  Output: validated + corrected Slide_JSON                                   │
│                                                                              │
│  Deterministic — NO LLM call (pure validation logic)                        │
│                                                                              │
│  Schema migration: auto-upgrades older schema versions to 1.0.0            │
│  Field migrations (LLM quirks handled):                                     │
│    - slide["chart"] → content["chart_data"] (labels+datasets → [{label,val}])│
│    - slide["table"] → content["table_data"] {headers, rows}                 │
│    - slide["comparison_data"] → content["comparison_data"]                  │
│    - content["title"] → slide["title"] (root-level extraction)              │
│    - content["subtitle"] → slide["subtitle"]                                │
│    - slide_type → type (with full mapping table)                            │
│    - layout_hint → visual_hint                                              │
│  Auto-corrections:                                                           │
│    - Missing slide_id → uuid4()                                             │
│    - Missing slide_number → sequential                                      │
│    - Missing visual_hint → inferred from slide_type                         │
│    - Empty chart_data → fallback from bullets or defaults                   │
│    - Empty table_data → fallback from bullets or defaults                   │
│    - Empty comparison_data → split bullets into left/right                  │
│  Content constraints:                                                        │
│    - Title truncation: max 8 words                                          │
│    - Bullet truncation: max 8 words per bullet                              │
│    - Bullet splitting: max 4 bullets per slide                              │
│  2 correction attempts before accepting result                              │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT 8: Quality Scoring                              Latency budget: 10s  │
│                                                                              │
│  Input:  validated slides[]                                                  │
│  Output: QualityScoreResult {                                                │
│    composite_score (1-10), 5 dimension scores,                               │
│    recommendations{}, requires_feedback_loop                                 │
│  }                                                                           │
│                                                                              │
│  Deterministic — NO LLM call (pure scoring logic)                           │
│                                                                              │
│  5 Dimensions (weighted average):                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Content Depth (25%)    — content ratio, bullet depth, data evidence │    │
│  │ Visual Appeal (20%)    — type diversity, density, icons/highlights  │    │
│  │ Structure Coherence (25%) — section coverage, order, flow          │    │
│  │ Data Accuracy (15%)    — chart/table/comparison data presence       │    │
│  │ Clarity (15%)          — title length, bullet count, jargon        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Feedback loop: if composite < 8.0 AND retries < 2                         │
│    → Remove agents 6,7,8 from completed_agents                              │
│    → Pipeline re-runs from Agent 6 (LLM Provider)                          │
│    → Max 2 feedback loop iterations                                         │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
Pipeline Finalized
  → Save slides to PostgreSQL (presentations.slides JSONB)
  → Cache Slide_JSON in Redis (6hr TTL)
  → Publish "complete" event to Redis Stream
  → Increment template usage counter
```

---

## 5. Data Flow Through the Pipeline

```
Topic: "Healthcare sector market analysis"
         │
         ▼ Agent 1
industry="healthcare", theme="deloitte", template="Healthcare Executive Briefing"
         │
         ▼ Agent 2
total_slides=12, sections=[
  Title(1), Agenda(1), Problem(2), Analysis(3),
  Evidence(2), Recommendations(2), Conclusion(1)
]
         │
         ▼ Agent 3
sections=["Clinical Overview", "Patient Impact", ...],
risks=["Regulatory compliance", "Cybersecurity threats", ...],
opportunities=["Digital health innovation", "Cost reduction", ...]
         │
         ▼ Agent 4
charts=[
  { type:"bar", labels:["Primary Care","Specialty","Hospital",...], data:[89,74,82,...] },
  { type:"line", labels:["Q1 2022","Q2 2022",...], data:[75,78,82,...] },
  ...
],
key_metrics={ patient_satisfaction:87.3, readmission_rate:8.2, ... }
         │
         ▼ Agent 5
system_prompt="You are an expert presentation designer..."
user_prompt="<topic>Healthcare...</topic><data_enrichment>KEY METRICS:
  - Patient Satisfaction: 87.3
  CHART DATA: [{"label":"Primary Care","value":89.0},...]
  ..."
         │
         ▼ Agent 6 (Claude API)
raw JSON: {
  "slides": [
    { "slide_type":"title", "title":"Healthcare Sector Market Analysis",
      "content":{ "subtitle":"Strategic Insights...", "icon_name":"Activity" } },
    { "slide_type":"chart", "title":"Patient Satisfaction Varies by Segment",
      "chart":{ "chart_type":"bar", "labels":["Primary Care",...], "datasets":[...] },
      "speaker_notes":"This chart shows..." },
    ...
  ]
}
         │
         ▼ Agent 7 (Validation)
Corrected JSON: {
  "slides": [
    { "type":"title", "slide_type":"title", "title":"Healthcare Sector Market Analysis",
      "subtitle":"Strategic Insights...",
      "content":{ "icon_name":"Activity" }, "visual_hint":"centered" },
    { "type":"chart", "slide_type":"chart",
      "title":"Patient Satisfaction Varies by Segment",
      "content":{ "chart_type":"bar",
        "chart_data":[{"label":"Primary Care","value":89.0},...],
        "highlight_text":"Primary Care leads at 89% satisfaction" },
      "visual_hint":"split-chart-right" },
    ...
  ]
}
         │
         ▼ Agent 8 (Quality Scoring)
composite_score=8.01
  content_depth=9.5, visual_appeal=5.5,
  structure_coherence=6.1, data_accuracy=10.0, clarity=10.0
requires_feedback_loop=False  ← score ≥ 8.0, no retry needed
```

---

## 6. Frontend Rendering Pipeline

```
SSE "slide_ready" event received
         │
         ▼
ProgressiveSlideViewer.parseSlide()
  → Resolve type: slide_type > type > visual_hint inference
  → Migrate chart: content.chart_data (list) or chart.labels+datasets → [{label,value}]
  → Migrate table: content.table_data.{headers,rows} → table_headers + table_rows (dict)
  → Migrate comparison: content.comparison_data → left_column + right_column
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
Theme applied via getThemeColors(theme)
  mckinsey:    primary=#003366, secondary=#0066CC, accent=#FF6600
  deloitte:    primary=#86BC25, secondary=#0076A8, accent=#00A3E0
  dark-modern: primary=#6C63FF, secondary=#FF6584, accent=#43E97B
```

---

## 7. Provider Failover Architecture

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
Call provider with timeout
  Success → record metrics, return response
  Failure → record failure, check circuit breaker
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
```

---

## 8. Database Schema (Key Tables)

```
presentations
  presentation_id  UUID PK
  user_id          UUID FK
  tenant_id        UUID FK
  topic            TEXT
  status           ENUM(queued, processing, completed, failed, cancelled)
  slides           JSONB          ← full slide array
  total_slides     INT
  selected_theme   TEXT
  detected_industry TEXT
  quality_score    FLOAT
  created_at       TIMESTAMP

pipeline_executions
  id               UUID PK
  presentation_id  UUID FK
  status           TEXT
  current_agent    TEXT
  error_message    TEXT
  prompt_id        TEXT
  started_at       TIMESTAMP

agent_states
  id               UUID PK
  execution_id     UUID FK
  agent_name       TEXT
  state            JSONB          ← agent output snapshot
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
```

---

## 9. Checkpoint & Recovery

Each agent persists its output to `agent_states` before the next agent starts. If the pipeline crashes mid-way:

```
Resume from checkpoint:
  1. Load latest PipelineExecution for presentation_id
  2. Load all AgentState records for execution_id
  3. Reconstruct PipelineContext from saved states
  4. Skip already-completed agents
  5. Resume from the first incomplete agent

Partial result delivery (on failure):
  → Best available slides saved to presentations.slides
  → Status set to "failed" (not lost)
  → User can retry via POST /presentations/{id}/regenerate
```

---

## 10. Caching Strategy

```
Redis Cache Keys:
  research:{industry}:{topic_hash}    TTL: 6 hours
  enrichment:{industry}:{topic_hash}  TTL: 6 hours
  slide_json:{industry}:{topic_hash}  TTL: 6 hours
  health:{provider}                   TTL: 30 seconds
  ratelimit:{user_id}                 TTL: 1 hour (sliding window)

Cache hit → skip agent entirely (research + enrichment = ~30s saved)
Cache miss → run agent, store result
Same topic + industry = identical deterministic output (seed-based)
```
