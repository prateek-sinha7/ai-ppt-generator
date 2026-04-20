# Design Document: AI Presentation Intelligence Platform

## Overview

The AI Presentation Intelligence Platform is an enterprise-grade system that transforms user topics into visually stunning, product-grade presentations comparable to Gamma and Beautiful.ai. The platform leverages a sophisticated multi-agent processing pipeline with multi-LLM provider support to deliver client-ready presentations with domain-specific insights, realistic business data, and consulting-grade storytelling across **any industry** — automatically detected from the topic.

### Core Design Principles

1. **Multi-Agent Architecture**: Sequential processing through specialized AI agents (Industry Classifier, Storyboarding, Research, Data Enrichment, Prompt Engineering, Validation, Quality Scoring) with clear separation of concerns
2. **Multi-LLM Provider Support**: Unified interface supporting Claude, OpenAI GPT-4, Groq, and Local LLM — provider is configured exclusively via `.env`, never via API or UI
3. **Single User Input**: User provides only a presentation topic; all other decisions (industry, template, audience, provider, theme) are made automatically by the backend
4. **Deterministic Structure Planning**: Storyboarding Agent has absolute authority over slide structure decisions, with LLMs filling content into predefined frameworks
5. **Visual Design Intelligence**: AI-powered layout optimization with strict content constraints and professional design standards
6. **Production-Ready Reliability**: Comprehensive state management, retry strategies, caching, monitoring, and graceful failure handling

### System Objectives

- **Visual Quality**: Gamma/Beautiful.ai level presentation engine with perfect visual quality and layout intelligence
- **Enterprise Scalability**: Multi-tenant architecture with rate limiting, security, and performance optimization
- **Content Intelligence**: Domain-specific insights with realistic business data and consulting-grade storytelling
- **Reliability**: Comprehensive error handling, state management, and recovery mechanisms
- **Observability**: Full traceability through LangSmith with multi-provider performance analytics

## Architecture

### High-Level System Architecture

The platform follows a layered architecture with clear separation between presentation logic, business processing, and infrastructure concerns:

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[React Frontend]
        Components[Slide Components]
        Themes[Presentation Themes]
    end
    
    subgraph "API Gateway Layer"
        API[FastAPI Backend]
        Auth[Authentication]
        RateLimit[Rate Limiting]
    end
    
    subgraph "Multi-Agent Pipeline"
        IC[Industry Classifier Agent]
        SB[Storyboarding Agent]
        RA[Research Agent]
        DEA[Data Enrichment Agent]
        PEA[Prompt Engineering Agent]
        VA[Validation Agent]
        QSA[Quality Scoring Agent]
    end
    
    subgraph "LLM Provider Layer"
        PF[Provider Factory]
        Claude[Claude API]
        OpenAI[OpenAI API]
        Groq[Groq API]
        Local[Local LLM]
    end
    
    subgraph "Core Services"
        SM[State Management]
        Cache[Caching Layer]
        Queue[Job Queue]
        Export[PPTX Export]
    end
    
    subgraph "Infrastructure"
        DB[(Database)]
        Redis[(Redis Cache)]
        Monitor[LangSmith]
        Docker[Container Platform]
    end
    
    UI --> API
    API --> IC
    IC --> SB
    SB --> RA
    RA --> DEA
    DEA --> PEA
    PEA --> PF
    PF --> Claude
    PF --> OpenAI
    PF --> Groq
    PF --> Local
    PF --> VA
    VA --> QSA
    QSA --> SM
    
    API --> Cache
    API --> Queue
    API --> Export
    SM --> DB
    Cache --> Redis
    Monitor --> PF
    
    Docker --> API
    Docker --> Queue
    Docker --> DB
    Docker --> Redis
```

### Multi-Agent Pipeline Architecture

The core processing pipeline follows a strict sequential flow with state persistence at each transition. The user provides **only a topic** — all other decisions are made automatically by the pipeline:

1. **Industry Classifier Agent**: Detects industry from the topic using open-ended LLM classification — works for **any industry**, not a fixed list — infers audience, selects best-fit template
2. **Storyboarding Agent**: Determines slide structure, count, and types using the detected industry and selected template as constraints
3. **Research Agent**: Analyzes topic and generates domain-specific insights using detected industry context
4. **Data Enrichment Agent**: Creates realistic business data, KPIs, and chart/table datasets appropriate for detected industry
5. **Prompt Engineering Agent**: Optimizes prompts for selected LLM provider capabilities
6. **LLM Provider Service**: Generates content using provider-specific optimized prompts
7. **Validation Agent**: Validates JSON structure and performs automatic error correction
8. **Quality Scoring Agent**: Evaluates presentation across five quantified dimensions

### Multi-LLM Provider Architecture

The provider layer implements a factory pattern with intelligent selection and failover:

```mermaid
graph LR
    subgraph "Provider Management"
        PF[Provider Factory]
        PHM[Provider Health Monitor]
        PM[Provider Metrics]
        FM[Failover Mechanism]
    end
    
    subgraph "Provider Implementations"
        CP[Claude Provider]
        OP[OpenAI Provider]
        GP[Groq Provider]
        LP[Local Provider]
    end
    
    PF --> CP
    PF --> OP
    PF --> GP
    PF --> LP
    
    PHM --> PF
    PM --> PF
    FM --> PF
```

### State Management and Consistency

Comprehensive state management ensures pipeline reliability and recovery:

- **Atomic Operations**: State persistence at each agent transition
- **Checkpoint Recovery**: Pipeline restart from any agent checkpoint
- **Concurrent Isolation**: Proper state isolation across concurrent requests
- **Audit Trails**: Complete execution history with provider selection events
- **Cleanup Policies**: Automated state cleanup with audit log preservation

## Components and Interfaces

### Core System Components

#### 1. Multi-Agent Pipeline Components

**Industry Classifier Agent** *(runs first — before all other agents)*
- **Purpose**: Automatically detect industry, infer audience, and select enterprise template from topic text alone — no user input required
- **Input**: Raw topic string (the only user-provided field)
- **Output**: `DetectedContext` — `{ industry, confidence, sub_sector, target_audience, selected_template_id, theme, compliance_context }`
- **Classification method**:
  1. Keyword matching against industry-specific term dictionaries
  2. Semantic similarity scoring via embedding comparison
  3. LLM-based classification as tiebreaker when confidence < 80%
- **Fallback**: If confidence < 80%, defaults to most semantically similar industry and logs for review
- **Template selection**: Matches detected industry + inferred topic type (risk assessment, market analysis, clinical study, etc.) to the best-fit system template

**Storyboarding Agent**
- **Purpose**: Deterministic slide structure planning with absolute authority over layout decisions
- **Input**: Topic analysis and industry context
- **Output**: Presentation_Plan_JSON with exact slide count, types, and section mapping
- **Authority**: Overrides any LLM structural suggestions through Conflict_Resolution_Engine

**Research Agent**
- **Purpose**: Deep topic analysis and industry-specific insight generation
- **Input**: User topic and auto-detected industry context from Industry_Classifier_Agent
- **Output**: Research findings with business insights, risks, and opportunities
- **Timeout**: 30 seconds with 3 retries and exponential backoff

**Data Enrichment Agent**
- **Purpose**: Realistic business data and KPI generation with chart preparation
- **Input**: Research findings and industry context
- **Output**: Datasets suitable for charts, tables, and visual representations
- **Features**: Seed-based generation for reproducibility, industry-specific data models

**Prompt Engineering Agent**
- **Purpose**: Multi-LLM provider prompt optimization and content generation coordination
- **Input**: Research data and selected LLM provider capabilities
- **Output**: Provider-optimized system prompts with JSON structure instructions
- **Optimization**: Provider-specific templates, few-shot examples, and instruction patterns

**Validation Agent**
- **Purpose**: JSON structure validation and automatic error correction
- **Input**: Raw LLM provider response
- **Output**: Validated Slide_JSON conforming to versioned schema
- **Features**: Schema validation, automatic correction, error escalation

**Quality Scoring Agent**
- **Purpose**: Multi-dimensional quality assessment with measurable metrics
- **Input**: Validated Slide_JSON
- **Output**: Quality_Score (1-10) with dimensional breakdown and improvement recommendations
- **Metrics**: Content depth, visual appeal, structure coherence, data accuracy, clarity

#### 2. LLM Provider System Components

**Provider Factory**
- **Interface**: Unified provider creation and management
- **Implementations**: Claude, OpenAI GPT-4, Groq, Local LLM providers
- **Configuration**: Reads `LLM_PRIMARY_PROVIDER` and `LLM_FALLBACK_PROVIDERS` from `.env` at startup — no runtime override possible
- **Startup validation**: Fails fast if primary provider key is missing or unreachable

**Provider Health Monitor**
- **Monitoring**: Response times, error rates, availability tracking
- **Thresholds**: 95% success rate for primary provider status
- **Actions**: Automatic failover, health status caching, recovery detection

**Provider Metrics**
- **Tracking**: Token usage, API calls, estimated costs per provider
- **Analytics**: Usage patterns, cost per presentation, efficiency metrics
- **Reporting**: Daily/monthly cost reports with trend analysis

#### 3. Design and Layout System Components

**Design Intelligence Layer**
- **Purpose**: AI-powered layout optimization based on content analysis
- **Features**: Content characteristic analysis, layout scoring, adaptation logic
- **Decisions**: Text-heavy → Split layouts, Data-heavy → Chart layouts, Comparison → Two-column

**Layout Decision Engine**
- **Rules**: Slide type to layout mapping (Title → Centered, Content → Bullet, etc.)
- **Constraints**: Max 4 bullets, 6-8 words per bullet, 8 words per title
- **Optimization**: Content density control, whitespace management, visual diversity

**Content Adjustment Engine**
- **Features**: Dynamic font sizing, line spacing optimization, element positioning
- **Constraints**: Readability limits, slide boundary prevention, overlap avoidance
- **Fallback**: Automatic slide splitting when content exceeds layout bounds

**Visual Hint System**
- **Enum Values**: centered, bullet-left, split-chart-right, split-table-left, two-column, highlight-metric
- **Purpose**: Standardized rendering instructions for frontend components
- **Validation**: Strict enum validation during JSON processing

#### 4. Frontend Architecture Components

**React Component System**
- **TitleSlide**: Centered layout with title/subtitle rendering
- **ContentSlide**: Bullet-left layout with structured content display
- **ChartSlide**: Split-chart-right layout with data visualization
- **TableSlide**: Split-table-left layout with tabular data presentation
- **ComparisonSlide**: Two-column layout for side-by-side content

**Frontend Data Contract**
- **TypeScript Interfaces**: Strict prop definitions for each slide component
- **Validation**: Runtime prop validation against defined interfaces
- **Consistency**: Deterministic rendering based solely on Slide_JSON data
- **Icon Library**: Lucide React used for all `icon_name` values; frontend maps string name to component
- **Highlight rendering**: `highlight_text` rendered as a visually distinct callout box per theme
- **Transitions**: `transition` field in slide content drives CSS animation class applied between slides

### Interface Specifications

#### 1. Slide_JSON Schema (Version 1.0.0)

```json
{
  "schema_version": "1.0.0",
  "presentation_id": "string",
  "total_slides": "number",
  "slides": [
    {
      "slide_id": "string",
      "slide_number": "number",
      "type": "enum[title|content|chart|table|comparison]",
      "title": "string (max 8 words)",
      "content": {
        "bullets": ["string (max 6-8 words each, max 4 bullets)"],
        "chart_data": "object (optional)",
        "table_data": "object (optional)",
        "comparison_data": "object (optional)",
        "icon_name": "string (optional, e.g. 'trending-up', 'shield', 'users')",
        "highlight_text": "string (optional, key metric or emphasis phrase)",
        "transition": "enum[fade|slide|none] (optional, default: fade)"
      },
      "visual_hint": "enum[centered|bullet-left|split-chart-right|split-table-left|two-column|highlight-metric]",
      "layout_constraints": {
        "max_content_density": 0.75,
        "min_whitespace_ratio": 0.25
      },
      "metadata": {
        "generated_at": "ISO8601 timestamp",
        "provider_used": "string",
        "quality_score": "number (1-10)"
      }
    }
  ]
}
```

#### 2. Auto-Detected Context Schema (Internal — not user input)

The `Industry_Classifier_Agent` produces this internally. It is never sent by the user — it is returned as read-only metadata in API responses:

```json
{
  "detected_industry":    "string (open-ended, e.g. 'healthcare', 'fintech', 'retail', 'manufacturing', 'education', etc.)",
  "confidence_score":     0.92,
  "sub_sector":           "clinical research",
  "target_audience":      "executives | analysts | technical | general",
  "selected_template_id": "uuid",
  "selected_template_name": "Healthcare Executive Briefing",
  "theme":                "mckinsey | deloitte | dark_modern",
  "compliance_context":   ["HIPAA", "FDA"],
  "classification_method": "keyword | semantic | llm"
}
```

This context is stored on the `presentations` table and surfaced in the status and result API responses as informational metadata — the user sees what was detected but cannot override it via the UI.

#### 3. Frontend_Data_Contract Interfaces

```typescript
interface TitleSlideProps {
  title: string;
  subtitle?: string;
  theme: PresentationTheme;
  visual_hint: 'centered';
}

interface ContentSlideProps {
  title: string;
  bullets: string[]; // max 4 items, max 8 words each
  visual_hint: 'bullet-left';
  theme: PresentationTheme;
}

interface ChartSlideProps {
  title: string;
  chart_data: ChartData;
  chart_type: 'bar' | 'line' | 'pie';
  visual_hint: 'split-chart-right';
  theme: PresentationTheme;
}
```

#### 4. API Endpoints

**Presentation Generation**
- `POST /api/v1/presentations` — Body: `{ topic }` (topic is the ONLY user input)
- `GET /api/v1/presentations/{id}/status` — Check generation status + detected context
- `GET /api/v1/presentations/{id}` — Retrieve completed Slide_JSON + metadata
- `POST /api/v1/presentations/{id}/regenerate` — Regenerate with different provider

**Provider Management** *(internal/admin only — not user-facing)*
- `GET /internal/providers` — List provider health status (admin only)
- `GET /internal/providers/{id}/metrics` — Usage and cost metrics (admin only)
- `POST /internal/providers/{id}/health-check` — Manual health check (admin only)
- Provider selection and configuration: `.env` only, requires restart

**Export and Templates**
- `GET /api/v1/presentations/{id}/export/pptx` — Export to PowerPoint
- `GET /api/v1/templates` — List available system templates (read-only for users)
- `GET /api/v1/presentations/{id}/detected-context` — View auto-detected industry, template, audience

## Data Models

### Core Data Entities

#### 1. Presentation Entity

```python
class Presentation:
    presentation_id:      str       # system-generated UUID
    user_id:              str       # authenticated user
    topic:                str       # ONLY field provided by user (max 500 chars)

    # --- Auto-detected by Industry_Classifier_Agent (never user input) ---
    detected_industry:    str       # open-ended string — any industry the LLM detects
    detection_confidence: float     # 0.0 - 1.0
    detected_sub_sector:  str       # e.g. "clinical research"
    inferred_audience:    str       # executives | analysts | technical | general
    selected_template_id: str       # UUID of auto-selected template
    selected_theme:       str       # mckinsey | deloitte | dark_modern
    compliance_context:   list[str] # e.g. ["HIPAA", "FDA"]

    # --- Generated content ---
    schema_version:       str
    total_slides:         int
    slides:               list[Slide]
    status:               PresentationStatus
    quality_score:        float
    created_at:           datetime
    updated_at:           datetime
```

#### 2. Slide Entity

```python
class Slide:
    slide_id: str
    slide_number: int
    type: SlideType  # title, content, chart, table, comparison
    title: str  # max 8 words
    content: SlideContent
    visual_hint: VisualHint
    layout_constraints: LayoutConstraints
    metadata: SlideMetadata
```

#### 3. Pipeline State Entity

```python
class PipelineState:
    execution_id: str
    presentation_id: str
    current_agent: AgentType
    agent_states: Dict[AgentType, AgentState]
    provider_history: List[ProviderAttempt]
    quality_scores: List[QualityScore]
    retry_count: int
    created_at: datetime
    updated_at: datetime
```

#### 4. Provider Configuration Entity

```python
class ProviderConfig:
    provider_id: str
    provider_type: ProviderType  # claude, openai, groq, local
    api_endpoint: str
    model_name: str
    max_tokens: int
    temperature: float
    rate_limits: RateLimits
    health_status: HealthStatus
    cost_per_token: float
    priority: int
```

### Data Relationships

```mermaid
erDiagram
    Presentation ||--o{ Slide : contains
    Presentation ||--|| PipelineState : tracks
    Presentation }o--|| User : belongs_to
    PipelineState ||--o{ AgentState : contains
    PipelineState ||--o{ ProviderAttempt : records
    ProviderAttempt }o--|| ProviderConfig : uses
    QualityScore }o--|| Presentation : evaluates
    Template ||--o{ Presentation : applies_to
```

### Data Storage Strategy

#### 1. Primary Database (PostgreSQL)
- **Presentations**: Core presentation data with JSONB for slide content
- **Users**: User accounts, authentication, and subscription tiers
- **Pipeline States**: Execution tracking with agent checkpoints
- **Provider Configs**: LLM provider settings and health status
- **Quality Metrics**: Historical quality scores and trends

#### 2. Cache Layer (Redis)
- **Provider Health**: Real-time health status with 30-second TTL
- **Generated Content**: Final Slide_JSON with composite key caching
- **Rate Limiting**: Per-user, per-provider, and system-wide counters
- **Session Data**: User sessions and temporary state

#### 3. Object Storage (S3/MinIO)
- **PPTX Exports**: Generated PowerPoint files with signed URLs
- **Template Assets**: Presentation templates and visual resources
- **Audit Logs**: Long-term storage of pipeline execution logs
- **Backup Data**: State snapshots for disaster recovery

### Data Consistency and Integrity

#### 1. ACID Compliance
- **Atomicity**: Pipeline state transitions as single transactions
- **Consistency**: Schema validation at all data entry points
- **Isolation**: Concurrent presentation generation with proper locking
- **Durability**: Write-ahead logging for critical state changes

#### 2. Data Validation
- **Schema Validation**: JSON Schema validation for all Slide_JSON
- **Business Rules**: Content constraints (word limits, bullet counts)
- **Referential Integrity**: Foreign key constraints and cascade rules
- **Input Sanitization**: XSS prevention and injection attack protection

#### 3. Backup and Recovery
- **Automated Backups**: Daily database backups with point-in-time recovery
- **State Snapshots**: Pipeline checkpoint preservation for 7 days
- **Cross-Region Replication**: Disaster recovery with RTO < 4 hours
- **Data Retention**: Audit log retention for compliance requirements

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Multi-Agent Pipeline Execution Sequence Invariant

*For any* presentation generation request, the multi-agent pipeline SHALL execute agents in the exact sequence: Storyboarding_Agent → Research_Agent → Data_Enrichment_Agent → Prompt_Engineering_Agent → LLM_Provider_Service → Validation_Agent → Quality_Scoring_Agent, with the Storyboarding_Agent having absolute authority over all structural decisions regardless of LLM provider responses.

**Validates: Requirements 4.1, 4.2, 43.1, 53.1**

### Property 2: JSON Schema Validation Round-Trip Consistency

*For any* valid Slide_JSON object conforming to the versioned schema, the validation process SHALL consistently identify valid structures, reject invalid structures with specific error messages, and ensure that parsing then formatting then re-parsing produces equivalent structured content.

**Validates: Requirements 5.1, 5.2, 25.1, 35.1, 52.1**

### Property 3: Content Generation Consistency and Constraints

*For any* valid topic and industry selection input, each agent SHALL produce output within specified constraints: Research_Agent generates 6-10 sections within 30 seconds, Data_Enrichment_Agent creates realistic industry-specific data within valid ranges, and all content generation is deterministic when using seed-based generation.

**Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 45.1, 57.1**

### Property 4: Provider Failover and Retry Logic Reliability

*For any* LLM provider configuration and failure scenario, the system SHALL attempt the primary provider first, implement automatic failover to secondary providers with exponential backoff retry logic, and maintain consistent behavior regardless of the specific failure type or provider used.

**Validates: Requirements 8.1, 8.2, 3.1**

### Property 5: Layout Decision Engine Determinism

*For any* slide content and type combination, the layout decision engine SHALL consistently map slide types to appropriate layouts (Title → Centered, Content → Bullet, Chart → Split-chart-right), automatically split slides when content exceeds thresholds (>4 bullets or length limits), and maintain visual constraints (max 0.75 content density, min 0.25 whitespace ratio).

**Validates: Requirements 14.1, 14.2, 18.1, 18.4**

### Property 6: Quality Scoring Mathematical Consistency

*For any* valid presentation content, the Quality_Scoring_Agent SHALL produce scores within the 1-10 range across all five dimensions, calculate composite scores as the correct weighted average (Content 25% + Visual 20% + Structure 25% + Data 15% + Clarity 15%), and achieve consistent scoring with <5% variance for identical content across multiple evaluations.

**Validates: Requirements 6.1, 6.2, 54.1, 54.5**

### Property 7: State Management and Idempotency Guarantees

*For any* presentation generation request with an idempotency key, the system SHALL persist pipeline state atomically at each agent transition, prevent duplicate job execution for identical idempotency keys, ensure retry operations don't create duplicate slides, and maintain state consistency across concurrent requests with proper isolation.

**Validates: Requirements 37.1, 37.2, 37.3, 56.1, 56.3**

### Property 8: Deterministic Frontend Rendering

*For any* identical Slide_JSON input, the frontend SHALL render slides purely based on the provided data without runtime interpretation, produce identical UI output across multiple renders, maintain cross-device rendering consistency, and ensure all layout decisions originate from backend-encoded visual_hint fields using standardized enum values.

**Validates: Requirements 38.1, 38.2, 38.3, 17.1, 17.3**

### Property 9: Industry-Specific Content Customization

*For any* topic submitted by a user, the system SHALL automatically detect the industry using open-ended LLM classification (not limited to a fixed list), generate content with appropriate industry-specific terminology, produce data within realistic industry value ranges, apply relevant compliance context, and maintain consistency in industry customization across all pipeline agents.

**Validates: Requirements 1.2, 2.1, 57.2, 57.3, 57.5**

### Property 10: Performance and Latency Budget Compliance

*For any* valid presentation request, each agent SHALL complete execution within specified latency budgets (Research 30s, Data Enrichment 20s, Prompt Engineering 5s, LLM Generation 40s, Validation 5s, Quality Scoring 10s), and the complete pipeline SHALL finish within 120 seconds while maintaining quality standards.

**Validates: Requirements 1.5, 4.5, 46.1**

## Error Handling

### Error Classification and Recovery Strategies

The platform implements a comprehensive error handling system with agent-specific recovery strategies and graceful degradation patterns.

#### 1. Agent-Specific Error Handling

**Research Agent Failures**
- **Retry Strategy**: 3 retries with 2-second exponential backoff
- **Fallback**: Cached industry data and template research patterns
- **Circuit Breaker**: Opens after >20% failure rate, routes to fallback immediately
- **Recovery**: Automatic primary path restoration when health improves

**Data Enrichment Agent Failures**
- **Retry Strategy**: 2 retries with 1-second linear backoff
- **Fallback**: Template datasets with industry-appropriate realistic ranges
- **Graceful Degradation**: Simplified data models when complex generation fails
- **Validation**: Data range validation before fallback acceptance

**Prompt Engineering Agent Failures**
- **Retry Strategy**: 1 retry with immediate fallback to default prompts
- **Fallback**: Provider-agnostic default prompt templates
- **Optimization**: Automatic prompt simplification for retry attempts
- **Logging**: Detailed prompt failure analysis for continuous improvement

**LLM Provider Service Failures**
- **Retry Strategy**: Provider-specific retry with automatic failover
- **Failover Sequence**: Primary → Secondary → Tertiary → Local (if available)
- **Backoff**: Exponential backoff per provider with jitter
- **Health Monitoring**: Real-time provider health assessment and routing

**Validation Agent Failures**
- **Retry Strategy**: 2 retries with schema correction attempts
- **Auto-Correction**: Intelligent JSON structure repair and field completion
- **Escalation**: Manual review queue for persistent validation failures
- **Schema Evolution**: Backward compatibility handling for version mismatches

**Quality Scoring Agent Failures**
- **Retry Strategy**: 1 retry, accept lower quality score if persistent failure
- **Degradation**: Simplified scoring metrics when full evaluation fails
- **Threshold Adjustment**: Dynamic quality thresholds based on system health
- **Monitoring**: Quality trend analysis and alert thresholds

#### 2. System-Level Error Handling

**Rate Limiting and Throttling**
- **Multi-Tier Limits**: Per-provider, per-user, and system-wide rate limiting
- **Intelligent Queuing**: Priority-based request queuing with estimated wait times
- **Graceful Degradation**: Simplified generation modes when approaching limits
- **User Communication**: Clear rate limit messaging with alternative options

**State Management Failures**
- **Atomic Operations**: All state transitions use database transactions
- **Checkpoint Recovery**: Pipeline restart from any agent checkpoint
- **Consistency Checks**: Regular state validation and corruption detection
- **Backup Strategy**: State snapshots with point-in-time recovery

**Provider Health Degradation**
- **Health Monitoring**: Continuous response time and error rate tracking
- **Automatic Failover**: Sub-95% success rate triggers provider switching
- **Load Balancing**: Intelligent request distribution based on provider health
- **Recovery Detection**: Automatic primary provider restoration

#### 3. User Experience Error Patterns

**Failure Communication Strategy**
- **Provider Failures**: "Switching to backup AI provider, please wait..."
- **Quality Failures**: "Enhancing presentation quality, this may take a moment..."
- **Timeout Failures**: "Generation is taking longer than expected, would you like to continue waiting or try a simpler version?"
- **Rate Limit Failures**: "High demand detected, estimated wait time: X minutes"

**Progressive Failure Handling**
- **Retry Options**: Automatic retry with different provider or simplified parameters
- **Partial Results**: Delivery of completed slides with option to finish later
- **Alternative Suggestions**: Cached similar presentations or template recommendations
- **Manual Override**: User control over retry strategies and quality thresholds

**Recovery and Rollback Options**
- **Previous Version Access**: Rollback to last successful generation
- **Partial Recovery**: Preservation of completed pipeline stages
- **Manual Intervention**: Support escalation for complex failure scenarios
- **State Preservation**: User session and progress maintenance across failures

#### 4. Monitoring and Alerting

**Error Metrics and Dashboards**
- **Agent Performance**: Individual agent success rates, latency, and error patterns
- **Provider Health**: Real-time provider status, cost tracking, and performance metrics
- **System Health**: Overall pipeline success rates, user satisfaction, and quality trends
- **Business Impact**: Cost per presentation, user retention, and feature adoption

**Automated Alerting**
- **Critical Failures**: Immediate alerts for system-wide outages or data corruption
- **Performance Degradation**: Alerts when latency budgets are consistently exceeded
- **Cost Thresholds**: Warnings when provider costs exceed configured limits
- **Quality Drops**: Notifications when presentation quality scores trend downward

**Continuous Improvement**
- **Error Pattern Analysis**: Machine learning-based failure prediction and prevention
- **Performance Optimization**: Automatic parameter tuning based on historical data
- **User Feedback Integration**: Error handling improvement based on user experience data
- **Provider Optimization**: Dynamic provider selection based on performance history

## Testing Strategy

### Comprehensive Testing Approach

The platform implements a dual testing strategy combining property-based testing for universal correctness guarantees with targeted unit and integration tests for specific scenarios and edge cases.

#### 1. Property-Based Testing Strategy

**Test Configuration**
- **Minimum Iterations**: 100 iterations per property test to ensure comprehensive input coverage
- **Property Test Library**: Hypothesis (Python) for backend services, fast-check (TypeScript) for frontend components
- **Test Data Generation**: Custom generators for industry-specific data, realistic business metrics, and valid JSON structures
- **Seed Management**: Reproducible test runs with configurable seeds for debugging

**Property Test Implementation**
Each correctness property will be implemented as a dedicated property-based test with the following tag format:

```python
# Feature: ai-presentation-intelligence-platform, Property 1: Multi-Agent Pipeline Execution Sequence Invariant
@given(presentation_request=presentation_request_generator())
def test_pipeline_execution_sequence_invariant(presentation_request):
    # Test implementation
```

**Property Test Coverage**
- **Pipeline Execution**: Sequence invariants, state transitions, agent coordination
- **JSON Processing**: Schema validation, round-trip consistency, error handling
- **Content Generation**: Industry customization, constraint compliance, reproducibility
- **Provider Management**: Failover logic, health monitoring, cost optimization
- **Quality Assessment**: Scoring consistency, mathematical correctness, variance limits

#### 2. Unit Testing Strategy

**Core Module Coverage**
- **Agent Implementations**: Individual agent logic, input validation, output formatting
- **Provider Clients**: API integration, error handling, response parsing
- **Validation Logic**: Schema validation, content constraints, error correction
- **Layout Engine**: Design decisions, content fitting, visual optimization
- **State Management**: Persistence, recovery, consistency checks

**Mock and Stub Strategy**
- **LLM Provider Mocking**: Controlled responses for testing agent logic without API costs
- **Database Mocking**: In-memory databases for fast unit test execution
- **External Service Stubs**: Predictable responses for third-party integrations
- **Time Mocking**: Controlled time progression for timeout and latency testing

#### 3. Integration Testing Strategy

**End-to-End Pipeline Testing**
- **Complete Workflows**: Full presentation generation from topic input to final output
- **Provider Integration**: Real API calls with test accounts and rate limiting
- **Database Integration**: Actual database operations with test data isolation
- **Cache Integration**: Redis integration with test cache namespaces

**Contract Testing**
- **API Contracts**: OpenAPI specification validation for all endpoints
- **Schema Contracts**: JSON Schema validation for all data structures
- **Component Contracts**: Frontend component prop validation and rendering consistency
- **Provider Contracts**: LLM provider response format validation

#### 4. Visual Regression Testing

**Frontend Rendering Consistency**
- **Snapshot Testing**: Automated visual snapshots for all slide component types
- **Cross-Browser Testing**: Rendering consistency across Chrome, Firefox, Safari, Edge
- **Responsive Testing**: Layout validation across different screen sizes and orientations
- **Theme Testing**: Visual consistency across all presentation themes

**PPTX Export Testing**
- **Format Preservation**: Validation that exported PPTX maintains visual fidelity
- **Cross-Platform Compatibility**: Testing exported files in PowerPoint, LibreOffice, Google Slides
- **Content Integrity**: Verification that all slide content is preserved in export

#### 5. Performance and Load Testing

**Latency Budget Validation**
- **Agent Performance**: Individual agent execution time validation under various loads
- **Pipeline Performance**: End-to-end generation time testing with concurrent requests
- **Provider Performance**: Response time monitoring across all LLM providers
- **Cache Performance**: Cache hit rate and response time optimization validation

**Scalability Testing**
- **Concurrent Users**: System behavior under high concurrent presentation generation
- **Rate Limiting**: Validation of rate limiting behavior under load
- **Resource Utilization**: Memory, CPU, and database performance under stress
- **Provider Failover**: Failover behavior validation under provider outages

#### 6. Security and Compliance Testing

**Input Validation Testing**
- **Injection Attacks**: SQL injection, XSS, and command injection prevention
- **Input Sanitization**: Malicious input handling and sanitization validation
- **Rate Limiting**: Abuse prevention and DDoS protection testing
- **Authentication**: User authentication and authorization testing

**Data Protection Testing**
- **Data Isolation**: Multi-tenant data isolation validation
- **Encryption**: Data encryption in transit and at rest validation
- **Audit Logging**: Comprehensive audit trail validation
- **Compliance**: Industry-specific compliance requirement validation

#### 7. Test Coverage and Quality Metrics

**Coverage Requirements**
- **Backend Coverage**: Minimum 80% code coverage for all backend services
- **Frontend Coverage**: Minimum 80% component and utility function coverage
- **Property Test Coverage**: 100% coverage of all defined correctness properties
- **Integration Coverage**: All API endpoints and critical user workflows

**Quality Metrics**
- **Test Reliability**: <1% flaky test rate with automatic retry and analysis
- **Test Performance**: Unit tests complete in <30 seconds, integration tests in <5 minutes
- **Defect Detection**: >95% defect detection rate in pre-production testing
- **Regression Prevention**: Zero regression defects in production releases

**Continuous Testing Integration**
- **CI/CD Pipeline**: Automated testing on every commit and pull request
- **Test Parallelization**: Parallel test execution for fast feedback cycles
- **Test Reporting**: Comprehensive test reports with coverage and performance metrics
- **Failure Analysis**: Automated failure analysis and developer notification


## Slide Transitions and Animation Design

### Transition Metadata in Slide_JSON

Each slide carries an optional `transition` field in its `content` object. The backend sets this during the Optimization phase of the Presentation Compiler based on slide type and position:

```typescript
type TransitionType = 'fade' | 'slide' | 'none';

// Default rules applied by Presentation Compiler:
// - First slide (title): 'none'
// - Slides following a chart/table: 'fade'
// - All other slides: 'slide'
```

### Frontend Transition Rendering

```typescript
// Transition applied via CSS class on slide container
const transitionClass: Record<TransitionType, string> = {
  fade:  'transition-opacity duration-500 ease-in-out',
  slide: 'transition-transform duration-400 ease-out translate-x-full',
  none:  '',
};

// Applied when slide becomes active in the viewer
function SlideViewer({ slide, isActive }: SlideViewerProps) {
  return (
    <div className={`slide-container ${isActive ? transitionClass[slide.content.transition ?? 'fade'] : ''}`}>
      <SlideRenderer slide={slide} />
    </div>
  );
}
```

### Rules
- Transitions are subtle and professional — no zoom, bounce, or spin effects
- Transition type is set by backend only; frontend never overrides it
- PPTX export maps `fade` → PowerPoint Fade, `slide` → PowerPoint Push, `none` → no transition

---

## Content Parser and Pretty Printer Design

### Slide Content Parser (Req 25)

The parser runs inside the **Validation Agent** after LLM output is received. It handles malformed or oversized content before schema validation.

```python
class SlideContentParser:
    MAX_BULLETS = 4
    MAX_BULLET_WORDS = 8
    MAX_TITLE_WORDS = 8

    def parse(self, raw_slide: dict) -> ParsedSlide:
        """
        1. Truncate title to MAX_TITLE_WORDS
        2. Split bullets exceeding MAX_BULLET_WORDS into shorter bullets
        3. If bullet count > MAX_BULLETS, split into two slides
        4. Validate chart/table data structure matches slide type
        5. Ensure round-trip: parse(format(parse(x))) == parse(x)
        """

    def split_slide(self, slide: dict) -> list[dict]:
        """Split an oversized slide into 2 slides preserving logical flow."""
        mid = len(slide['content']['bullets']) // 2
        slide_a = {**slide, 'content': {'bullets': slide['content']['bullets'][:mid]}}
        slide_b = {**slide, 'content': {'bullets': slide['content']['bullets'][mid:]}}
        slide_b['title'] = slide['title'] + ' (cont.)'
        return [slide_a, slide_b]
```

**Round-trip property** (Req 25.5): `parse(format(parse(x))) == parse(x)` — enforced by property-based test using Hypothesis.

### Slide Content Pretty Printer (Req 26)

The pretty printer produces human-readable outlines for debugging, review, and audit logs.

```python
class SlidePrettyPrinter:
    def format(self, presentation: dict, output_format: str = 'text') -> str:
        """
        Supported output_format values:
          'text'     → plain text outline (default, for logs)
          'markdown' → markdown with headers and bullets (for review UI)
          'json'     → indented JSON (for debugging)
        """

    def format_slide(self, slide: dict) -> str:
        lines = [f"[{slide['slide_number']}] {slide['type'].upper()}: {slide['title']}"]
        for b in slide.get('content', {}).get('bullets', []):
            lines.append(f"  • {b}")
        if slide['content'].get('chart_data'):
            lines.append(f"  [CHART: {slide['content']['chart_data'].get('chart_type')}]")
        if slide['content'].get('table_data'):
            lines.append(f"  [TABLE: {len(slide['content']['table_data'].get('rows', []))} rows]")
        return '\n'.join(lines)
```

**Performance**: Formatting 50 slides completes in < 2 seconds (Req 26.5) — pure in-memory string operations, no I/O.

---

## LangChain Integration Design

### Role of LangChain (Req 29)

LangChain is used **only for agent orchestration and LLM provider abstraction** — not for business logic. The abstraction layer is kept thin so LangChain can be swapped without affecting agent logic.

```
┌─────────────────────────────────────────────────────┐
│              Agent Orchestration Layer               │
│  (LangChain: chains, memory, callbacks, tracing)     │
├─────────────────────────────────────────────────────┤
│              Agent Business Logic Layer              │
│  (Pure Python: Research, DataEnrichment, etc.)       │
├─────────────────────────────────────────────────────┤
│              LLM Provider Abstraction                │
│  (LangChain: ChatAnthropic, ChatOpenAI, ChatGroq)    │
└─────────────────────────────────────────────────────┘
```

### LangChain Components Used

| Component | Usage |
|---|---|
| `ChatAnthropic` | Claude provider client |
| `ChatOpenAI` | OpenAI provider client |
| `ChatGroq` | Groq provider client |
| `LangChain callbacks` | LangSmith tracing hooks |
| `RunnableSequence` | Pipeline stage chaining |
| `ConversationBufferMemory` | Agent context between stages |
| `StructuredOutputParser` | Enforce JSON output from LLM |

### Provider Abstraction Pattern

```python
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq

class ProviderFactory:
    def create(self, provider_type: str) -> BaseChatModel:
        match provider_type:
            case "claude":
                return ChatAnthropic(model="claude-3-5-sonnet-20241022",
                                     api_key=settings.ANTHROPIC_API_KEY)
            case "openai":
                return ChatOpenAI(model="gpt-4o",
                                  api_key=settings.OPENAI_API_KEY)
            case "groq":
                return ChatGroq(model="llama-3.3-70b-versatile",
                                api_key=settings.GROQ_API_KEY)
            case "local":
                return ChatOpenAI(base_url=settings.LOCAL_LLM_ENDPOINT,
                                  api_key="not-needed")
```

### LangChain Independence Principle

- All agent business logic is in pure Python classes — zero LangChain imports in agent logic files
- LangChain is only imported in the `orchestrator` and `provider_factory` modules
- If LangChain is replaced, only those two modules change — agents are unaffected

---

## Advanced Frontend UX Design

### Slide Reordering (Req 51.1)

```typescript
// Drag-and-drop via @dnd-kit/core
import { DndContext, closestCenter } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';

function SlideReorderPanel({ slides, onReorder }: Props) {
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (active.id !== over?.id) {
      const reordered = arrayMove(slides, activeIndex, overIndex);
      // PATCH /api/v1/presentations/{id}/slides/reorder
      onReorder(reordered);
    }
  };
  return (
    <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={slides} strategy={verticalListSortingStrategy}>
        {slides.map(s => <SortableSlideThumb key={s.slide_id} slide={s} />)}
      </SortableContext>
    </DndContext>
  );
}
```

**Reorder API endpoint:**
```
PATCH /api/v1/presentations/{id}/slides/reorder
  Body: { "slide_order": ["slide_id_1", "slide_id_3", "slide_id_2", ...] }
  Response: { updated_presentation_id, new_version }
  # Creates a new presentation version; validates narrative flow after reorder
```

### Export Preview Mode (Req 51.3)

- Triggered via `GET /api/v1/presentations/{id}/export/preview`
- Returns a signed URL to a server-rendered PDF preview (generated via headless Chromium)
- Preview shows exact PPTX layout including fonts, colors, and chart rendering
- Preview URL expires after 1 hour

### Collaborative Features (Req 51.5)

Collaborative features are scoped to the same tenant. Implementation uses optimistic locking:

| Feature | Implementation |
|---|---|
| Comments | `presentation_comments` table; `GET/POST /presentations/{id}/comments` |
| Slide locking | `slide_locks` table (already designed); prevents concurrent edits |
| Approval workflow | `presentation_status` field: `draft → in_review → approved`; role-based transitions |
| Suggestions | Stored as pending slide edits; reviewer can accept/reject per suggestion |

**Reorder API endpoint addition to Complete API Contract:**
```
PATCH /api/v1/presentations/{id}/slides/reorder
  Body: { slide_order: ["uuid", "uuid", ...] }
  Response: { presentation_id, new_version }

GET   /api/v1/presentations/{id}/comments
POST  /api/v1/presentations/{id}/comments
  Body: { slide_id?, comment_text }

PATCH /api/v1/presentations/{id}/status
  Body: { status: "in_review" | "approved" | "draft" }
  Response: { presentation_id, status }
```

---

## Industry Classifier Agent Design

### Overview

The `Industry_Classifier_Agent` is the **first agent** in the pipeline. It runs before any other agent and produces the `DetectedContext` that all subsequent agents consume. The user never sees or interacts with this step — it is fully automatic.

### Classification Pipeline

```
topic (string)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Step 1: Keyword Matching (fast, deterministic)      │
│  - Match against industry term dictionaries          │
│  - healthcare_terms: ["patient", "clinical", "HIPAA",│
│    "hospital", "diagnosis", "pharma", "EHR", ...]    │
│  - insurance_terms:  ["premium", "actuarial",        │
│    "underwriting", "claims", "policy", "risk", ...]  │
│  - automobile_terms: ["vehicle", "OEM", "fleet",     │
│    "manufacturing", "EV", "supply chain", ...]       │
│  → produces: { industry, keyword_score }             │
└──────────────────────┬──────────────────────────────┘
                       │ if keyword_score < 0.6
                       ▼
┌─────────────────────────────────────────────────────┐
│  Step 2: Semantic Similarity (embedding-based)       │
│  - Embed topic using sentence-transformers           │
│  - Compare cosine similarity to industry centroids   │
│  → produces: { industry, semantic_score }            │
└──────────────────────┬──────────────────────────────┘
                       │ if semantic_score < 0.8
                       ▼
┌─────────────────────────────────────────────────────┐
│  Step 3: LLM Classification (structured output)      │
│  - Prompt: "Identify the industry this topic         │
│    belongs to. Return the industry name as a         │
│    short label (e.g. 'healthcare', 'fintech',        │
│    'retail', 'manufacturing', 'education',           │
│    'logistics', 'real estate', etc.).                │
│    Return JSON: { industry, confidence, sub_sector,  │
│    audience, compliance_flags }"                     │
│  → produces: { industry, confidence, sub_sector,     │
│    target_audience, compliance_context }             │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Template Selection                                  │
│  - Match (industry + sub_sector) → best-fit template │
│  - Fallback: use default industry template           │
│  → produces: { selected_template_id, theme }         │
└─────────────────────────────────────────────────────┘
```

### Industry Term Dictionaries (Seed Examples — Extensible)

The keyword matching step uses seed dictionaries as a fast first-pass. These are **examples only** — the system is not limited to these industries. The LLM classification step handles any industry not covered by keyword matching:

```python
# Seed dictionaries for fast keyword matching (Step 1)
# New industries can be added here without changing core logic
INDUSTRY_SEED_TERMS = {
    "healthcare": [
        "patient", "clinical", "hospital", "diagnosis", "treatment",
        "pharma", "EHR", "HIPAA", "FDA", "medical", "physician",
        "drug", "therapy", "biotech", "surgical", "radiology"
    ],
    "insurance": [
        "premium", "policy", "underwriting", "actuarial", "claims",
        "risk", "reinsurance", "liability", "coverage", "deductible"
    ],
    "automobile": [
        "vehicle", "car", "OEM", "fleet", "manufacturing", "EV",
        "supply chain", "dealership", "automotive", "engine"
    ],
    "finance": [
        "banking", "investment", "portfolio", "equity", "bond",
        "fintech", "trading", "hedge fund", "asset management"
    ],
    "technology": [
        "software", "SaaS", "cloud", "API", "platform", "startup",
        "AI", "machine learning", "cybersecurity", "DevOps"
    ],
    "retail": [
        "e-commerce", "consumer", "merchandise", "store", "SKU",
        "inventory", "supply chain", "omnichannel", "loyalty"
    ],
    "education": [
        "university", "curriculum", "student", "learning", "EdTech",
        "training", "certification", "academic", "school"
    ],
    # ... any new industry can be added here
    # If topic doesn't match any seed, LLM classification handles it
}
```

**Key principle**: If keyword matching score < 0.6 for all known industries, the system falls through to LLM classification which can identify **any** industry from the topic text — no hardcoded limit.

### DetectedContext Output Schema

```json
{
  "industry":             "healthcare",
  "confidence":           0.94,
  "sub_sector":           "clinical research",
  "target_audience":      "executives",
  "selected_template_id": "uuid",
  "selected_template_name": "Healthcare Executive Briefing",
  "theme":                "mckinsey",
  "compliance_context":   ["HIPAA", "FDA"],
  "classification_method": "keyword"
}
```

### Audience Inference Rules

| Topic Language Signals | Inferred Audience |
|---|---|
| "board", "CEO", "strategy", "ROI", "investment" | executives |
| "data", "metrics", "KPI", "analysis", "trends" | analysts |
| "architecture", "API", "implementation", "system" | technical |
| No strong signals | general |

### Template Auto-Selection Matrix

Templates are matched by detected industry + topic type signal. The system ships with templates for common industries and falls back to a **generic enterprise template** for any unrecognised industry:

| Industry | Sub-Sector Signal | Selected Template |
|---|---|---|
| healthcare | "research", "study", "trial" | Clinical Research Summary |
| healthcare | "compliance", "regulation" | Compliance Report |
| healthcare | default | Healthcare Executive Briefing |
| insurance | "risk", "assessment" | Risk Assessment |
| insurance | "market", "product" | Market Analysis |
| insurance | default | Risk Assessment |
| automobile | "safety", "recall" | Safety Report |
| automobile | "market", "consumer" | Market Research |
| automobile | default | Manufacturing Update |
| finance / fintech | "investment", "portfolio" | Investment Analysis |
| finance / fintech | default | Financial Executive Briefing |
| technology | "product", "launch" | Product Launch |
| technology | default | Technology Strategy |
| retail | default | Market & Consumer Analysis |
| education | default | Research & Insights |
| **any other industry** | any | **Generic Enterprise Briefing** (fallback) |

The **Generic Enterprise Briefing** template follows the standard consulting structure (Title → Agenda → Problem → Analysis → Evidence → Recommendations → Conclusion) and works for any industry.


### API Design Principles

- All endpoints versioned under `/api/v1/`
- JWT Bearer token authentication on all protected routes
- Idempotency-Key header supported on all mutation endpoints
- Rate limit headers returned on every response: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Standard error envelope: `{ "error": { "code": "string", "message": "string", "details": {} } }`

### Authentication Endpoints

```
POST   /api/v1/auth/register          Register new user
POST   /api/v1/auth/login             Login, returns JWT access + refresh tokens
POST   /api/v1/auth/refresh           Refresh access token
POST   /api/v1/auth/logout            Invalidate tokens
GET    /api/v1/auth/me                Get current user profile
```

### Presentation Generation Endpoints

```
POST   /api/v1/presentations
  Headers: Authorization, Idempotency-Key
  Body: { topic }                          ← ONLY field required from user
  Response: { job_id, presentation_id, status: "queued", estimated_seconds }
  # Backend auto-detects: industry, template, audience, theme, provider

GET    /api/v1/presentations/{id}/status
  Response: {
    status, current_agent, progress_pct, estimated_remaining_seconds,
    streaming_url?,
    detected_industry,      ← informational, read-only
    selected_template,      ← informational, read-only
    inferred_audience       ← informational, read-only
  }

GET    /api/v1/presentations/{id}
  Response: Slide_JSON (schema v1.0.0) + metadata.detected_context

POST   /api/v1/presentations/{id}/regenerate
  Body: { quality_threshold?, slide_ids? }
  Response: { job_id, status }
  # Provider is selected automatically by backend based on .env config

PATCH  /api/v1/presentations/{id}/slides/{slide_id}
  Body: { title?, content?, visual_hint? }
  Response: updated Slide

POST   /api/v1/presentations/{id}/slides/{slide_id}/regenerate
  Body: { instructions? }
  Response: { job_id }
  # Provider selected automatically from .env config

POST   /api/v1/presentations/{id}/slides/{slide_id}/lock
  Response: { locked: true, locked_by, locked_at }

DELETE /api/v1/presentations/{id}/slides/{slide_id}/lock
  Response: { locked: false }

GET    /api/v1/presentations/{id}/versions
  Response: [{ version, created_at, change_summary }]

GET    /api/v1/presentations/{id}/versions/{version}
  Response: Slide_JSON at that version

POST   /api/v1/presentations/{id}/rollback
  Body: { target_version }
  Response: { presentation_id, version }

GET    /api/v1/presentations/{id}/diff
  Query: from_version, to_version
  Response: { added_slides, removed_slides, modified_slides }
```

### Export Endpoints

```
POST   /api/v1/presentations/{id}/export/pptx
  Response: { export_job_id, status }

GET    /api/v1/presentations/{id}/export/pptx/status
  Response: { status, download_url?, expires_at? }

GET    /api/v1/presentations/{id}/export/preview
  Response: { preview_url, expires_at }
```

### Job Management Endpoints

```
GET    /api/v1/jobs/{job_id}
  Response: { job_id, type, status, created_at, updated_at, result?, error? }

DELETE /api/v1/jobs/{job_id}
  Response: { cancelled: true }
```

### Provider Management Endpoints

> **Provider selection is infrastructure-only — configured via `.env`, never via API or UI.**
> These endpoints are internal/admin-only and not accessible to regular users.

```
# Internal admin endpoints (require admin role + internal network)
GET    /internal/providers
  Response: [{ provider_id, type, status, health_score, priority }]

GET    /internal/providers/{id}/metrics
  Response: { token_usage, api_calls, cost_usd, avg_latency_ms, error_rate }

POST   /internal/providers/{id}/health-check
  Response: { healthy, latency_ms, error? }
```

No `PATCH /providers/{id}/config` endpoint exists — all provider config changes require a `.env` update and service restart.

### Template Endpoints

```
GET    /api/v1/templates
  Query: industry?, audience?
  Response: [{ template_id, name, industry, slide_count, preview_url }]

GET    /api/v1/templates/{id}
  Response: full template definition

POST   /api/v1/templates
  Body: { name, industry, slides_structure, theme }
  Response: created template

POST   /api/v1/presentations/{id}/apply-template
  Body: { template_id }
  Response: { job_id }
```

### User & Tenant Management Endpoints

```
GET    /api/v1/users/me
GET    /api/v1/users/me/usage
  Response: { presentations_this_hour, presentations_today, cost_usd_today }

GET    /api/v1/admin/tenants                    (admin only)
POST   /api/v1/admin/tenants                    (admin only)
GET    /api/v1/admin/tenants/{id}/usage         (admin only)
```

### Prompt Management Endpoints

```
GET    /api/v1/prompts
  Response: [{ prompt_id, version, agent_type, provider, created_at, effectiveness_score }]

GET    /api/v1/prompts/{id}
  Response: full prompt with metadata

POST   /api/v1/prompts/{id}/rollback
  Body: { target_version }
  Response: { prompt_id, version }
```

### Streaming Endpoint

```
GET    /api/v1/presentations/{id}/stream
  Protocol: Server-Sent Events (SSE)
  Events:
    { event: "agent_start",    data: { agent, timestamp } }
    { event: "agent_complete", data: { agent, duration_ms } }
    { event: "slide_ready",    data: { slide_number, slide_id, partial_slide_json } }
    { event: "quality_score",  data: { score, dimensions } }
    { event: "complete",       data: { presentation_id, total_slides } }
    { event: "error",          data: { code, message, recoverable } }
```

### Cache Management Endpoints

```
GET    /api/v1/cache/stats
  Response: { hit_rate, total_entries, storage_bytes, cost_savings_usd }

DELETE /api/v1/cache/presentations/{id}
  Response: { invalidated: true }

POST   /api/v1/cache/warm
  Body: { topics: [], industry, theme }
  Response: { job_id }
```


## Database Schema

### Design Decisions

- **PostgreSQL** as primary store; JSONB for flexible slide content
- **Row-Level Security (RLS)** for multi-tenant isolation — every table has `tenant_id`
- **UUID v4** primary keys throughout
- **Soft deletes** via `deleted_at` on user-facing entities

### Tables

#### `tenants`
```sql
CREATE TABLE tenants (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL,
  plan          TEXT NOT NULL DEFAULT 'free',  -- free | premium | enterprise
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at    TIMESTAMPTZ
);
```

#### `users`
```sql
CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id),
  email         TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'member',  -- admin | member | viewer
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at    TIMESTAMPTZ
);
CREATE INDEX idx_users_tenant ON users(tenant_id);
```

#### `refresh_tokens`
```sql
CREATE TABLE refresh_tokens (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### `presentations`
```sql
CREATE TABLE presentations (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID NOT NULL REFERENCES tenants(id),
  user_id               UUID NOT NULL REFERENCES users(id),
  topic                 TEXT NOT NULL,           -- ONLY user-provided field
  -- Auto-detected by Industry_Classifier_Agent (never user input):
  detected_industry     TEXT,                    -- open-ended string, any industry (e.g. 'healthcare', 'fintech', 'retail')
  detection_confidence  NUMERIC(4,2),            -- 0.0 - 1.0
  sub_sector            TEXT,
  target_audience       TEXT NOT NULL DEFAULT 'executives',
  selected_template_id  UUID REFERENCES templates(id),
  theme                 TEXT NOT NULL DEFAULT 'mckinsey',
  compliance_context    JSONB,                   -- ["HIPAA", "FDA"] etc.
  classification_method TEXT,                    -- keyword | semantic | llm
  -- Generation state:
  schema_version        TEXT NOT NULL DEFAULT '1.0.0',
  status                TEXT NOT NULL DEFAULT 'queued',
  current_version       TEXT NOT NULL DEFAULT 'v1.0',
  quality_score         NUMERIC(4,2),
  slide_count           INT,
  slides                JSONB,
  idempotency_key       TEXT UNIQUE,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at            TIMESTAMPTZ
);
CREATE INDEX idx_presentations_tenant   ON presentations(tenant_id);
CREATE INDEX idx_presentations_user     ON presentations(user_id);
CREATE INDEX idx_presentations_status   ON presentations(status);
CREATE INDEX idx_presentations_idem_key ON presentations(idempotency_key);
CREATE INDEX idx_presentations_industry ON presentations(detected_industry);
```

#### `presentation_versions`
```sql
CREATE TABLE presentation_versions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  presentation_id UUID NOT NULL REFERENCES presentations(id),
  version         TEXT NOT NULL,   -- v1.0, v1.1, v2.0
  slides          JSONB NOT NULL,
  change_summary  TEXT,
  created_by      UUID REFERENCES users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pv_presentation ON presentation_versions(presentation_id);
CREATE UNIQUE INDEX idx_pv_version ON presentation_versions(presentation_id, version);
```

#### `slide_locks`
```sql
CREATE TABLE slide_locks (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  presentation_id UUID NOT NULL REFERENCES presentations(id),
  slide_id        TEXT NOT NULL,
  locked_by       UUID NOT NULL REFERENCES users(id),
  locked_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at      TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '1 hour',
  UNIQUE(presentation_id, slide_id)
);
```

#### `pipeline_executions`
```sql
CREATE TABLE pipeline_executions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  presentation_id UUID NOT NULL REFERENCES presentations(id),
  job_id          UUID NOT NULL,
  status          TEXT NOT NULL DEFAULT 'running',
  -- running | completed | failed | cancelled
  current_agent   TEXT,
  retry_count     INT NOT NULL DEFAULT 0,
  cost_usd        NUMERIC(10,6),
  started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at    TIMESTAMPTZ,
  error_message   TEXT
);
CREATE INDEX idx_pe_presentation ON pipeline_executions(presentation_id);
CREATE INDEX idx_pe_job          ON pipeline_executions(job_id);
```

#### `agent_states`
```sql
CREATE TABLE agent_states (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  execution_id UUID NOT NULL REFERENCES pipeline_executions(id),
  agent_type   TEXT NOT NULL,
  -- storyboarding | research | data_enrichment | prompt_engineering
  -- llm_generation | validation | quality_scoring
  status       TEXT NOT NULL,  -- pending | running | completed | failed | skipped
  input_data   JSONB,
  output_data  JSONB,
  retry_count  INT NOT NULL DEFAULT 0,
  latency_ms   INT,
  started_at   TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  error_message TEXT
);
CREATE INDEX idx_as_execution ON agent_states(execution_id);
```

#### `provider_configs`
```sql
-- Populated at startup from .env — never written via API
-- Read-only at runtime; changes require .env update + restart
CREATE TABLE provider_configs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_type TEXT NOT NULL,  -- claude | openai | groq | local
  api_endpoint  TEXT NOT NULL,
  model_name    TEXT NOT NULL,
  max_tokens    INT NOT NULL DEFAULT 4096,
  temperature   NUMERIC(3,2) NOT NULL DEFAULT 0.7,
  priority      INT NOT NULL DEFAULT 1,  -- 1=primary, 2=first fallback, etc.
  is_primary    BOOLEAN NOT NULL DEFAULT false,
  enabled       BOOLEAN NOT NULL DEFAULT true,
  cost_per_1k_tokens NUMERIC(8,6),
  rate_limit_rpm INT,
  loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()  -- when .env was last loaded
);
```

#### `provider_health_logs`
```sql
CREATE TABLE provider_health_logs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_id   UUID NOT NULL REFERENCES provider_configs(id),
  success       BOOLEAN NOT NULL,
  latency_ms    INT,
  error_code    TEXT,
  recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_phl_provider ON provider_health_logs(provider_id, recorded_at DESC);
```

#### `provider_usage`
```sql
CREATE TABLE provider_usage (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  execution_id    UUID REFERENCES pipeline_executions(id),
  provider_id     UUID NOT NULL REFERENCES provider_configs(id),
  tenant_id       UUID NOT NULL REFERENCES tenants(id),
  tokens_input    INT NOT NULL DEFAULT 0,
  tokens_output   INT NOT NULL DEFAULT 0,
  cost_usd        NUMERIC(10,6),
  recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pu_tenant   ON provider_usage(tenant_id, recorded_at DESC);
CREATE INDEX idx_pu_provider ON provider_usage(provider_id, recorded_at DESC);
```

#### `prompts`
```sql
CREATE TABLE prompts (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_type        TEXT NOT NULL,
  provider_type     TEXT NOT NULL,
  version           TEXT NOT NULL,  -- semver: 1.0.0
  content           TEXT NOT NULL,
  is_active         BOOLEAN NOT NULL DEFAULT true,
  effectiveness_score NUMERIC(4,2),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  deprecated_at     TIMESTAMPTZ
);
CREATE UNIQUE INDEX idx_prompts_active ON prompts(agent_type, provider_type)
  WHERE is_active = true;
```

#### `quality_scores`
```sql
CREATE TABLE quality_scores (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  presentation_id UUID NOT NULL REFERENCES presentations(id),
  execution_id    UUID REFERENCES pipeline_executions(id),
  composite_score NUMERIC(4,2) NOT NULL,
  content_depth   NUMERIC(4,2),
  visual_appeal   NUMERIC(4,2),
  structure_coherence NUMERIC(4,2),
  data_accuracy   NUMERIC(4,2),
  clarity         NUMERIC(4,2),
  recommendations JSONB,
  scored_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_qs_presentation ON quality_scores(presentation_id);
```

#### `templates`
```sql
CREATE TABLE templates (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID REFERENCES tenants(id),  -- NULL = system template
  name            TEXT NOT NULL,
  industry        TEXT NOT NULL,
  target_audience TEXT,
  slide_structure JSONB NOT NULL,
  theme           TEXT NOT NULL,
  usage_count     INT NOT NULL DEFAULT 0,
  created_by      UUID REFERENCES users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_templates_industry ON templates(industry);
```

#### `audit_logs`
```sql
CREATE TABLE audit_logs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID NOT NULL REFERENCES tenants(id),
  user_id     UUID REFERENCES users(id),
  action      TEXT NOT NULL,
  resource    TEXT NOT NULL,
  resource_id UUID,
  metadata    JSONB,
  ip_address  INET,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_tenant ON audit_logs(tenant_id, created_at DESC);
```


## Authentication and RBAC Design

### Authentication Flow

```
1. User POSTs /auth/login with email + password
2. Server verifies password_hash (bcrypt, cost=12)
3. Server issues:
   - Access token:  JWT, signed HS256, TTL=15min, payload: { sub, tenant_id, role }
   - Refresh token: opaque UUID, stored as hash in refresh_tokens table, TTL=30 days
4. Client sends: Authorization: Bearer <access_token> on every request
5. On 401, client POSTs /auth/refresh with refresh token to get new access token
6. Logout revokes refresh token (sets revoked_at)
```

### RBAC Roles and Permissions

| Permission | admin | member | viewer |
|---|---|---|---|
| Create presentation | ✅ | ✅ | ❌ |
| View own presentations | ✅ | ✅ | ✅ |
| View all tenant presentations | ✅ | ❌ | ❌ |
| Edit/regenerate slides | ✅ | ✅ | ❌ |
| Export PPTX | ✅ | ✅ | ✅ |
| Manage templates | ✅ | ✅ | ❌ |
| Manage provider configs | ✅ | ❌ | ❌ |
| View cost analytics | ✅ | ❌ | ❌ |
| Manage users | ✅ | ❌ | ❌ |
| View audit logs | ✅ | ❌ | ❌ |

### Multi-Tenant Isolation

- Every database table includes `tenant_id`
- PostgreSQL Row-Level Security (RLS) policies enforce tenant isolation at DB level:
  ```sql
  ALTER TABLE presentations ENABLE ROW LEVEL SECURITY;
  CREATE POLICY tenant_isolation ON presentations
    USING (tenant_id = current_setting('app.tenant_id')::uuid);
  ```
- Application sets `app.tenant_id` from JWT on every DB connection
- No cross-tenant queries possible even with SQL injection

### Security Controls

- **HTTPS only**: TLS 1.2+ enforced, HTTP redirected
- **Input sanitization**: Pydantic models validate all inputs; HTML stripped from text fields
- **API key storage**: Provider API keys stored encrypted (AES-256) in environment; never logged
- **Sensitive data**: No PII or slide content in application logs; structured logging with field masking
- **CORS**: Strict origin whitelist; credentials mode required
- **CSP headers**: Content-Security-Policy on all frontend responses


## Async Queue and Background Job System

### Technology Stack

- **Queue broker**: Redis (via Celery) — chosen for simplicity, speed, and existing Redis dependency
- **Worker framework**: Celery with `gevent` concurrency pool
- **Task routing**: Dedicated queues per priority tier

### Queue Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI Backend                      │
│  POST /presentations → enqueue task → return job_id     │
└──────────────────────────┬──────────────────────────────┘
                           │ publish
                    ┌──────▼──────┐
                    │    Redis    │
                    │  (Broker)   │
                    └──────┬──────┘
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   [high-priority]   [default]        [export]
   premium users     standard         pptx jobs
          │                │
          ▼                ▼
   ┌─────────────────────────────┐
   │     Celery Workers (N)      │
   │  - pipeline_task            │
   │  - slide_regenerate_task    │
   │  - export_pptx_task         │
   │  - cache_warm_task          │
   └─────────────────────────────┘
```

### Task Definitions

```python
# Task: full pipeline generation
@celery.task(bind=True, name="pipeline.generate", max_retries=0)
def generate_presentation_task(self, presentation_id: str, execution_id: str):
    # Runs: Storyboarding → Research → DataEnrichment →
    #       PromptEngineering → LLMGeneration → Validation → QualityScoring
    # Updates agent_states table at each step
    # Updates presentations.status throughout

# Task: single slide regeneration
@celery.task(bind=True, name="pipeline.regenerate_slide", max_retries=2)
def regenerate_slide_task(self, presentation_id: str, slide_id: str, options: dict):
    pass

# Task: PPTX export
@celery.task(bind=True, name="export.pptx", max_retries=3)
def export_pptx_task(self, presentation_id: str):
    # Uses python-pptx to build file
    # Uploads to S3/MinIO
    # Returns signed download URL (TTL=1 hour)
    pass
```

### Job Status Lifecycle

```
queued → processing → completed
                   ↘ failed
                   ↘ cancelled
```

### Frontend Polling / Streaming

- **Polling**: `GET /api/v1/jobs/{job_id}` every 2 seconds (fallback)
- **Streaming**: `GET /api/v1/presentations/{id}/stream` via SSE (preferred)
  - SSE connection kept alive during pipeline execution
  - Each agent completion emits an event with partial slide data
  - Frontend renders slides progressively as they arrive
  - On disconnect, client reconnects with `Last-Event-ID` header for resumption

### Concurrency and Scaling

- Default: 4 Celery workers × 10 gevent coroutines = 40 concurrent tasks
- High-priority queue processed by dedicated worker pool
- Worker autoscaling via container orchestration (Kubernetes HPA or docker-compose scale)
- Redis Sentinel for broker high availability


## Cost Control Design

### Cost Ceiling Enforcement

Every pipeline execution has a hard cost budget enforced at the `LLM_Provider_Service` level:

```python
class CostController:
    MAX_LLM_CALLS_PER_REQUEST = 4       # across all providers + retries
    DEFAULT_COST_CEILING_USD  = 0.50    # configurable per tenant plan
    DIMINISHING_RETURN_DELTA  = 0.5     # min quality improvement per retry

    def should_allow_llm_call(self, execution: PipelineExecution) -> bool:
        if execution.llm_call_count >= self.MAX_LLM_CALLS_PER_REQUEST:
            return False
        if execution.cost_usd >= execution.cost_ceiling_usd:
            return False
        return True

    def should_continue_feedback_loop(
        self, scores: list[float]
    ) -> bool:
        if len(scores) < 2:
            return True
        improvement = scores[-1] - scores[-2]
        return improvement >= self.DIMINISHING_RETURN_DELTA
```

### Cost Tracking Flow

```
LLM call completes
  → record tokens_input, tokens_output in provider_usage
  → compute cost_usd = (tokens / 1000) * cost_per_1k_tokens
  → accumulate on pipeline_executions.cost_usd
  → check against cost_ceiling_usd
  → if exceeded: terminate pipeline, deliver best result so far
```

### Cost Alerts

- Tenant daily cost threshold configurable (default: $10/day)
- Alert sent via webhook/email when 80% of threshold reached
- Hard stop at 100% — new requests queued until next billing period
- Cost analytics available at `/api/v1/users/me/usage` and admin dashboard

### Provider Cost Optimization

- When multiple providers meet quality threshold, select cheapest
- Cost-per-quality-point tracked: `cost_usd / quality_score`
- Provider priority auto-adjusted weekly based on cost efficiency
- Groq preferred for speed/cost; Claude preferred for quality-critical requests

## Caching Design

### Cache Key Strategy

```python
# Final Slide_JSON cache (Redis, TTL=24h)
cache_key = sha256(f"{topic}:{industry}:{theme}:{provider_config_hash}:{prompt_version}")

# Research cache (Redis, TTL=6h)
research_key = sha256(f"research:{topic}:{industry}")

# Data enrichment cache (Redis, TTL=6h)
data_key = sha256(f"data:{topic}:{industry}:{seed}")

# Provider health cache (Redis, TTL=30s)
health_key = f"health:{provider_id}"

# Rate limit counters (Redis, TTL=sliding window)
rate_key_user     = f"rl:user:{user_id}:{window_minute}"
rate_key_provider = f"rl:provider:{provider_id}:{window_minute}"
rate_key_system   = f"rl:system:{window_minute}"
```

### Cache Invalidation Rules

| Event | Invalidated Keys |
|---|---|
| Prompt version updated | All final output keys using that prompt version |
| Provider config changed | Provider health key |
| User manually regenerates | Final output key for that presentation |
| Schema version bumped | All final output keys (full flush) |

### Cache Warming

- Background task runs nightly for top-50 topics per industry
- Triggered manually via `POST /api/v1/cache/warm`
- Cache hit rate target: 90%+ for repeated requests within 24 hours
- Cache analytics tracked in Redis and exposed via API


## Streaming Engine Design

### Server-Sent Events (SSE) Architecture

```
Client                          FastAPI                      Celery Worker
  │                                │                               │
  │  GET /presentations/{id}/stream│                               │
  ├───────────────────────────────►│                               │
  │                                │  subscribe to Redis channel   │
  │                                │  presentations:{id}:events    │
  │                                │◄──────────────────────────────┤
  │  event: agent_start (research) │                               │
  │◄───────────────────────────────┤  publish event                │
  │                                │◄──────────────────────────────┤
  │  event: slide_ready (slide 1)  │                               │
  │◄───────────────────────────────┤  publish event                │
  │                                │◄──────────────────────────────┤
  │  event: complete               │                               │
  │◄───────────────────────────────┤  publish event                │
```

### SSE Event Schema

```typescript
// agent_start
{ event: "agent_start", id: "evt_001", data: { agent: "research", timestamp: "ISO8601" } }

// agent_complete
{ event: "agent_complete", id: "evt_002", data: { agent: "research", duration_ms: 12400 } }

// slide_ready (progressive rendering)
{ event: "slide_ready", id: "evt_003", data: {
    slide_number: 1,
    slide_id: "uuid",
    slide: { /* partial Slide_JSON for this slide */ }
  }
}

// quality_score
{ event: "quality_score", id: "evt_010", data: { score: 8.4, dimensions: { content: 9, visual: 8, ... } } }

// complete
{ event: "complete", id: "evt_011", data: { presentation_id: "uuid", total_slides: 12 } }

// error
{ event: "error", id: "evt_err", data: { code: "PROVIDER_TIMEOUT", message: "...", recoverable: true } }
```

### Reconnection Handling

- Client sends `Last-Event-ID` header on reconnect
- Server replays missed events from Redis stream (events stored for 5 minutes)
- If presentation already complete, server sends all events immediately then `complete`

### Cancellation

- Client closes SSE connection → server detects disconnect
- `DELETE /api/v1/jobs/{job_id}` sends cancellation signal via Redis pub/sub
- Worker checks cancellation flag between agent transitions
- Partial results preserved in database; status set to `cancelled`

## Presentation Versioning Design

### Version Numbering

- Format: `v{major}.{minor}` — e.g., `v1.0`, `v1.1`, `v2.0`
- Minor bump: slide content edits, regeneration of individual slides
- Major bump: full regeneration, theme change, template application

### Version Storage

- Full `slides` JSONB snapshot stored in `presentation_versions` per version
- `presentations.current_version` points to active version
- `presentations.slides` always reflects current version (denormalized for read performance)

### Diff Algorithm

```python
def compute_diff(version_a: dict, version_b: dict) -> dict:
    slides_a = {s["slide_id"]: s for s in version_a["slides"]}
    slides_b = {s["slide_id"]: s for s in version_b["slides"]}
    return {
        "added_slides":    [s for sid, s in slides_b.items() if sid not in slides_a],
        "removed_slides":  [s for sid, s in slides_a.items() if sid not in slides_b],
        "modified_slides": [
            {"slide_id": sid, "changes": deep_diff(slides_a[sid], slides_b[sid])}
            for sid in slides_a if sid in slides_b and slides_a[sid] != slides_b[sid]
        ]
    }
```

### Rollback Flow

```
POST /presentations/{id}/rollback { target_version: "v1.0" }
  → load presentation_versions WHERE version = "v1.0"
  → copy slides JSONB to presentations.slides
  → create new version entry (e.g., v2.1) with change_summary = "Rollback to v1.0"
  → update presentations.current_version = "v2.1"
  → invalidate cache for this presentation
```

## Prompt Versioning Design

### Prompt Lifecycle

```
create prompt (v1.0.0, is_active=true)
  → test effectiveness via quality_score tracking
  → create improved prompt (v1.1.0, is_active=true)
  → old prompt auto-deprecated (deprecated_at = now())
  → rollback: set v1.0.0 is_active=true, v1.1.0 is_active=false
```

### Prompt Metadata Stored Per Presentation

Each `pipeline_executions` record stores which prompt version was used per agent, enabling full traceability:

```json
{
  "prompts_used": {
    "research":          { "prompt_id": "uuid", "version": "1.2.0" },
    "data_enrichment":   { "prompt_id": "uuid", "version": "1.0.0" },
    "prompt_engineering":{ "prompt_id": "uuid", "version": "2.1.0" }
  }
}
```

### Effectiveness Tracking

- After each pipeline completes, `quality_score` linked back to prompt versions used
- `prompts.effectiveness_score` updated as rolling average
- Prompts with effectiveness < 6.0 flagged for review

## Presentation Compiler Design

### Compilation Phases

```
Phase 0: Industry Classification (Industry_Classifier_Agent)
  - Detect industry from topic using open-ended LLM classification
    (any industry — not limited to a fixed list)
  - Infer target audience from topic language and complexity
  - Select best-fit enterprise template (falls back to Generic Enterprise Briefing)
  - Determine theme (McKinsey, Deloitte, Dark Modern) based on detected industry
  - Apply relevant compliance context inferred by LLM for the detected industry
  - Output: DetectedContext stored on presentation record

Phase 1: Analysis
  - Assess topic complexity (simple | moderate | complex)
  - Determine optimal slide count based on complexity + detected industry
  - Identify required slide types for consulting structure

Phase 2: Planning (Storyboarding Agent)
  - Generate Presentation_Plan_JSON using detected template as constraint
  - Enforce: min 5, max 25 slides
  - Ensure no more than 2 consecutive slides of same type
  - Map sections to slide types per selected template

Phase 3: Generation (LLM Provider Service)
  - LLM fills content into predefined slide structures
  - Storyboarding plan + industry context passed as hard constraints in prompt

Phase 4: Optimization (Design Intelligence Layer)
  - Check content density per slide (max 0.75)
  - Auto-split overcrowded slides
  - Rebalance visual diversity if needed

Phase 5: Validation (Validation Agent)
  - Schema validation
  - Content constraint validation (word limits, bullet counts)
  - visual_hint enum validation

Phase 6: Quality Assessment (Quality Scoring Agent)
  - Score across 5 dimensions
  - Trigger feedback loop if score < 8
```

### Presentation_Plan_JSON Schema

```json
{
  "plan_id": "uuid",
  "topic": "string",
  "industry": "string (open-ended, auto-detected)",
  "total_slides": 12,
  "sections": [
    { "name": "Title",           "slide_count": 1, "slide_types": ["title"] },
    { "name": "Agenda",          "slide_count": 1, "slide_types": ["content"] },
    { "name": "Problem",         "slide_count": 2, "slide_types": ["content", "chart"] },
    { "name": "Analysis",        "slide_count": 3, "slide_types": ["content", "table", "chart"] },
    { "name": "Evidence",        "slide_count": 2, "slide_types": ["chart", "comparison"] },
    { "name": "Recommendations", "slide_count": 2, "slide_types": ["content", "content"] },
    { "name": "Conclusion",      "slide_count": 1, "slide_types": ["content"] }
  ],
  "visual_diversity_check": true,
  "created_at": "ISO8601"
}
```

## Design Intelligence Layer

### Layout Scoring Algorithm

```python
def score_layout(slide: Slide) -> float:
    scores = []

    # Visual balance: content vs whitespace
    density = compute_content_density(slide)
    scores.append(1.0 - abs(density - 0.6))  # optimal at 60%

    # Type-content alignment
    if slide.type == "chart" and slide.visual_hint == "split-chart-right":
        scores.append(1.0)
    elif slide.type == "comparison" and slide.visual_hint == "two-column":
        scores.append(1.0)
    else:
        scores.append(0.5)

    # Readability: title word count
    title_words = len(slide.title.split())
    scores.append(1.0 if title_words <= 8 else max(0, 1 - (title_words - 8) * 0.1))

    return sum(scores) / len(scores)
```

### Layout Recommendation Rules

| Content Characteristic | Recommended Layout | visual_hint |
|---|---|---|
| Single metric / KPI | Highlight metric | `highlight-metric` |
| 1-4 bullet points | Bullet left | `bullet-left` |
| Chart + supporting text | Split chart right | `split-chart-right` |
| Table + supporting text | Split table left | `split-table-left` |
| Two options / comparison | Two column | `two-column` |
| Title / intro slide | Centered | `centered` |

### Visual Diversity Enforcement

- Compiler tracks slide type sequence
- If 2 consecutive slides have same `visual_hint`, third is forced to different type
- Ensures varied, engaging presentation flow

## Design Token System

### Token Definitions (Req 16)

All spacing, typography, and color values are defined as tokens. Frontend uses these exclusively — no hardcoded values allowed.

```typescript
// tokens.ts — single source of truth for all visual constants
export const spacing = {
  xs:  '4px',
  sm:  '8px',
  md:  '16px',
  lg:  '24px',
  xl:  '32px',
} as const;

export const typography = {
  title:    { fontSize: '32px', fontWeight: 700, lineHeight: 1.2 },
  subtitle: { fontSize: '22px', fontWeight: 600, lineHeight: 1.3 },
  body:     { fontSize: '16px', fontWeight: 400, lineHeight: 1.5 },
  caption:  { fontSize: '12px', fontWeight: 400, lineHeight: 1.4 },
} as const;

export const themes = {
  mckinsey: {
    primary:    '#003366',
    secondary:  '#0066CC',
    accent:     '#FF6600',
    background: '#FFFFFF',
    surface:    '#F5F7FA',
    text:       '#1A1A1A',
  },
  deloitte: {
    primary:    '#86BC25',
    secondary:  '#0076A8',
    accent:     '#FFFFFF',
    background: '#FFFFFF',
    surface:    '#F0F0F0',
    text:       '#1A1A1A',
  },
  dark_modern: {
    primary:    '#6C63FF',
    secondary:  '#00D4AA',
    accent:     '#FF6584',
    background: '#1A1A2E',
    surface:    '#16213E',
    text:       '#E0E0E0',
  },
} as const;

export const grid = {
  baseUnit: 8,   // 8px grid — all layout values must be multiples of 8
} as const;
```

### Backend Token Reference

The backend references token names (not values) in Slide_JSON layout instructions. The frontend resolves names to values at render time:

```json
{
  "layout_instructions": {
    "padding": "lg",
    "gap": "sm",
    "title_style": "title",
    "body_style": "body"
  }
}
```

### Token Validation

- Backend validates all `layout_instructions` token names against the token registry at JSON validation time
- Frontend throws a runtime error if an unknown token name is encountered
- Token changes require a schema version bump to maintain backward compatibility

## Deterministic Data Generation Design (Req 45)

### Seed-Based Generation

```python
class DataEnrichmentAgent:
    def generate(self, topic: str, industry: str, seed: int | None = None) -> dict:
        # Seed derived from topic hash if not provided — ensures reproducibility
        effective_seed = seed or abs(hash(f"{topic}:{industry}")) % (2**32)
        rng = random.Random(effective_seed)
        return self._generate_with_rng(rng, industry)
```

### Industry-Specific Bounded Ranges

Seed ranges are defined for well-known industries. For any unrecognised industry, the LLM generates realistic ranges dynamically based on the detected industry context:

```python
# Seed ranges for known industries (fast path)
INDUSTRY_DATA_RANGES = {
    "healthcare": {
        "market_size_usd_bn":     (50,   500),
        "growth_rate_pct":        (3,    12),
        "patient_volume_k":       (10,   500),
        "cost_per_patient_usd":   (1000, 50000),
    },
    "insurance": {
        "premium_revenue_usd_bn": (1,    100),
        "loss_ratio_pct":         (55,   85),
        "claims_count_k":         (10,   1000),
        "avg_claim_usd":          (500,  25000),
    },
    "automobile": {
        "units_sold_k":           (10,   5000),
        "revenue_usd_bn":         (1,    200),
        "market_share_pct":       (1,    35),
    },
    "finance": {
        "aum_usd_bn":             (1,    500),
        "return_pct":             (5,    25),
        "portfolio_count_k":      (1,    100),
    },
    "technology": {
        "arr_usd_mn":             (1,    1000),
        "user_growth_pct":        (10,   200),
        "churn_rate_pct":         (2,    15),
    },
    # For any other industry: LLM generates realistic ranges dynamically
}

def get_data_ranges(industry: str) -> dict:
    if industry in INDUSTRY_DATA_RANGES:
        return INDUSTRY_DATA_RANGES[industry]
    # Fallback: LLM generates industry-appropriate KPI ranges
    return llm_generate_industry_ranges(industry)
```

### Audit Trail

Every data generation call logs: `{ seed, industry, topic_hash, generated_at, agent_version }` — stored in `agent_states.output_data` for full reproducibility.

## LangSmith Observability Design (Req 33)

### Integration Architecture

```python
from langchain.callbacks import LangChainTracer
from langsmith import Client

# Configured at startup from LANGSMITH_API_KEY env var
tracer = LangChainTracer(project_name=settings.LANGSMITH_PROJECT)

# Every agent run tagged with provider, industry, execution_id
def run_agent(agent, input_data, execution_id: str, provider: str):
    return agent.invoke(
        input_data,
        config={
            "callbacks": [tracer],
            "tags": [f"provider:{provider}", f"execution:{execution_id}"],
            "metadata": { "execution_id": execution_id, "provider": provider }
        }
    )
```

### What Gets Traced

| Event | LangSmith Data |
|---|---|
| Agent start/end | Duration, input/output tokens, latency |
| Provider call | Model name, prompt version, response time |
| Provider failover | From/to provider, failure reason |
| Quality score | Score per dimension, retry count |
| Pipeline complete | Total cost, total latency, final quality score |

### Alerting Thresholds

- Agent latency > budget → warning tag in LangSmith
- Provider error rate > 5% → alert via LangSmith webhook
- Quality score < 6 after all retries → alert for manual review
- Cost per request > ceiling → alert + auto-terminate

## Presentation Versioning — Branching and Merging (Req 50.3)

### Branching

A branch is created when a user regenerates from a specific version rather than the latest:

```
POST /api/v1/presentations/{id}/rollback { target_version: "v1.0" }
→ creates v2.0 (branch from v1.0, not from v1.5)
→ stored in presentation_versions with parent_version = "v1.0"
```

### Merging

Merge takes selected slides from one version and applies them to another:

```
POST /api/v1/presentations/{id}/merge
  Body: {
    "source_version": "v1.2",
    "target_version": "v2.0",
    "slide_ids": ["slide_id_1", "slide_id_3"]   ← take these slides from source
  }
  Response: { new_version: "v2.1", merged_slide_count: 2 }
```

Merge creates a new version combining slides from both versions. Conflicts (same slide_number modified in both) are resolved by preferring the `source_version` slides.

**Database addition:**
```sql
ALTER TABLE presentation_versions
  ADD COLUMN parent_version TEXT,
  ADD COLUMN merge_source   TEXT;
```



### Template Structure

```json
{
  "template_id": "uuid",
  "name": "Healthcare Executive Briefing",
  "industry": "healthcare",
  "target_audience": "executives",
  "theme": "mckinsey",
  "slide_structure": [
    { "position": 1, "type": "title",      "visual_hint": "centered",          "section": "Title" },
    { "position": 2, "type": "content",    "visual_hint": "bullet-left",       "section": "Agenda" },
    { "position": 3, "type": "content",    "visual_hint": "bullet-left",       "section": "Problem" },
    { "position": 4, "type": "chart",      "visual_hint": "split-chart-right", "section": "Analysis" },
    { "position": 5, "type": "table",      "visual_hint": "split-table-left",  "section": "Evidence" },
    { "position": 6, "type": "comparison", "visual_hint": "two-column",        "section": "Options" },
    { "position": 7, "type": "content",    "visual_hint": "highlight-metric",  "section": "Recommendation" },
    { "position": 8, "type": "content",    "visual_hint": "bullet-left",       "section": "Conclusion" }
  ]
}
```

### System Templates Per Industry

The platform ships with templates for common industries. Any unrecognised industry uses the **Generic Enterprise Briefing** template:

| Industry | Template Name | Slides |
|---|---|---|
| Healthcare | Executive Briefing | 8 |
| Healthcare | Clinical Research Summary | 12 |
| Healthcare | Compliance Report | 10 |
| Insurance | Risk Assessment | 10 |
| Insurance | Market Analysis | 12 |
| Insurance | Product Launch | 8 |
| Automobile | Safety Report | 10 |
| Automobile | Market Research | 12 |
| Automobile | Manufacturing Update | 8 |
| Finance / Fintech | Investment Analysis | 10 |
| Finance / Fintech | Financial Executive Briefing | 8 |
| Technology | Product Launch | 8 |
| Technology | Technology Strategy | 10 |
| Retail | Market & Consumer Analysis | 10 |
| Education | Research & Insights | 10 |
| **Any industry** | **Generic Enterprise Briefing** | **10** |

### Template Application Flow

```
POST /presentations/{id}/apply-template { template_id }
  → load template slide_structure
  → create new pipeline execution with template as Storyboarding constraint
  → LLM fills content into template structure
  → creates new presentation version
  → returns job_id for status tracking
```

## Deployment Architecture

### Docker Compose (Development)

```yaml
services:
  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://...
      - REDIS_URL=redis://redis:6379
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - GROQ_API_KEY=${GROQ_API_KEY}
      - LANGSMITH_API_KEY=${LANGSMITH_API_KEY}
    depends_on: [db, redis]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]

  worker:
    build: ./backend
    command: celery -A app.worker worker --loglevel=info -Q high-priority,default,export
    environment: *backend-env
    depends_on: [db, redis]

  frontend:
    build: ./frontend
    environment:
      - VITE_API_URL=http://localhost:8000

  db:
    image: postgres:16
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]

  redis:
    image: redis:7-alpine
    volumes: [redisdata:/data]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    volumes: [miniodata:/data]
```

### Health Check Endpoints

```
GET /health          → { status: "ok", version, timestamp }
GET /health/ready    → checks DB + Redis + at least 1 LLM provider reachable
GET /health/live     → simple liveness probe
```

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Cache / Queue
REDIS_URL=redis://host:6379

# LLM Provider Configuration (ONLY place to change provider — no API/UI override)
LLM_PRIMARY_PROVIDER=claude          # claude | openai | groq | local
LLM_FALLBACK_PROVIDERS=groq,openai   # ordered fallback list, comma-separated

# Provider API Keys (only keys for configured providers are required)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
LOCAL_LLM_ENDPOINT=http://ollama:11434

# Observability
LANGSMITH_API_KEY=ls__...
LANGSMITH_PROJECT=ai-presentation-platform

# Security
JWT_SECRET_KEY=<256-bit random>
JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=30

# Cost Controls
DEFAULT_COST_CEILING_USD=0.50
MAX_LLM_CALLS_PER_REQUEST=4

# Storage
S3_BUCKET=presentations-exports
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
```
