# Research Agent Integration Guide

## Overview

The Research Agent is the third agent in the multi-agent pipeline, responsible for deep topic analysis and industry-specific insight generation. It runs after the Industry Classifier Agent and Storyboarding Agent.

## Features

### Core Capabilities
- **Topic Analysis**: Breaks topics into 6-10 logical sections appropriate for the detected industry
- **Domain Insights**: Generates business risks, opportunities, and terminology
- **Timeout Handling**: 30-second timeout with 3 retries using exponential backoff (2s base)
- **Fallback Strategy**: Uses cached industry data when all LLM retries fail
- **State Persistence**: Stores findings in agent_states for subsequent agent consumption

### Supported Industries
- Healthcare
- Insurance
- Finance
- Technology
- Retail
- Manufacturing
- Logistics
- Real Estate
- Default (generic enterprise)

## Usage

### Basic Usage

```python
from app.agents.research import research_agent

# Analyze a topic
findings = await research_agent.analyze_topic(
    topic="Digital transformation strategy for healthcare providers",
    industry="healthcare",
    execution_id="exec-123",
    sub_sector="clinical research",  # Optional
    target_audience="executives",    # Optional: executives, analysts, technical, general
)

# Access findings
print(f"Sections: {findings.sections}")
print(f"Risks: {findings.risks}")
print(f"Opportunities: {findings.opportunities}")
print(f"Terminology: {findings.terminology}")
print(f"Method: {findings.method}")  # "llm" or "cached"

# Store findings for subsequent agents
await research_agent.store_findings(findings, execution_id="exec-123")
```

### Pipeline Integration

```python
# In the multi-agent pipeline orchestrator

# Step 1: Industry Classification (already completed)
detected_context = await industry_classifier.classify(topic, execution_id)

# Step 2: Storyboarding (already completed)
presentation_plan = storyboarding_agent.generate_presentation_plan(
    topic=topic,
    industry=detected_context.industry,
)

# Step 3: Research Agent (NEW)
research_findings = await research_agent.analyze_topic(
    topic=topic,
    industry=detected_context.industry,
    execution_id=execution_id,
    sub_sector=detected_context.sub_sector,
    target_audience=detected_context.target_audience,
)

# Store findings for subsequent agents
await research_agent.store_findings(research_findings, execution_id)

# Step 4: Data Enrichment Agent (uses research findings)
# Step 5: Prompt Engineering Agent (uses research findings)
# ... continue pipeline
```

## Output Schema

### ResearchFindings

```python
@dataclass
class ResearchFindings:
    topic: str                    # Original topic
    industry: str                 # Detected industry
    sections: List[str]           # 6-10 logical sections
    risks: List[str]              # 3-6 business risks
    opportunities: List[str]      # 3-6 business opportunities
    terminology: List[str]        # 5-10 domain-specific terms
    context_summary: str          # 2-3 sentence summary
    method: str                   # "llm" or "cached"
    execution_id: str             # Pipeline execution ID
    created_at: str               # ISO8601 timestamp
```

## Error Handling

### Timeout and Retry Logic

The agent implements robust error handling:

1. **First Attempt**: 30-second timeout
2. **Retry 1**: 2-second backoff, then retry
3. **Retry 2**: 4-second backoff, then retry
4. **Retry 3**: 8-second backoff, then retry
5. **Fallback**: Use cached industry data

### Cached Data Fallback

When all LLM retries fail, the agent automatically falls back to cached industry data:

```python
# Cached data includes:
# - Industry-specific sections (6-10)
# - Common risks and opportunities
# - Standard terminology
# - Generic context summary

findings = await research_agent.analyze_topic(...)
if findings.method == "cached":
    logger.warning("Using cached data due to LLM failures")
```

## Configuration

### Timeout Settings

```python
# In research.py
TIMEOUT_SECONDS = 30          # Timeout per LLM attempt
MAX_RETRIES = 3               # Maximum retry attempts
BASE_BACKOFF_SECONDS = 2.0    # Base exponential backoff
```

### Audience Targeting

The agent adapts prompts based on target audience:

- **executives**: Strategic implications, ROI, business impact
- **analysts**: Data-driven insights, metrics, analytical frameworks
- **technical**: Technical details, implementation, architecture
- **general**: Balanced business and technical perspectives

## Testing

### Unit Tests

```bash
# Run Research Agent tests
pytest tests/test_research_agent.py -v

# Run with coverage
pytest tests/test_research_agent.py --cov=app.agents.research
```

### Test Coverage

- Topic analysis with LLM
- Cached data fallback
- Timeout and retry logic
- Research findings storage
- Different audience types
- Multiple industries

## Performance

### Latency Budget

- **Target**: < 30 seconds per attempt
- **Maximum**: 90 seconds (3 retries × 30s)
- **Typical**: 5-15 seconds (successful LLM call)

### Caching Strategy

Cached industry data provides instant fallback:
- No external API calls
- Deterministic results
- Industry-appropriate content

## Monitoring

### Key Metrics

- Success rate (LLM vs cached)
- Average latency per industry
- Retry frequency
- Timeout occurrences

### Logging

All operations are logged with structlog:

```python
logger.info("research_analysis_started", topic=topic, industry=industry)
logger.info("research_llm_attempt", attempt=1)
logger.warning("research_llm_timeout", timeout_seconds=30)
logger.info("research_analysis_completed_llm", elapsed_ms=5234)
logger.warning("research_llm_failed_using_cached_data")
```

## Next Steps

After the Research Agent completes:

1. **Data Enrichment Agent**: Uses research findings to generate realistic business data
2. **Prompt Engineering Agent**: Incorporates research insights into LLM prompts
3. **LLM Provider Service**: Generates content based on research context
4. **Validation Agent**: Validates generated content
5. **Quality Scoring Agent**: Evaluates final presentation quality

## References

- **Requirements**: Req 1, 55
- **Design**: Components and Interfaces
- **Task**: 9. Implement Research Agent
