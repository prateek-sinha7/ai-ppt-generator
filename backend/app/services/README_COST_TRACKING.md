# Cost Tracking System

## Overview

The Cost Tracking System provides comprehensive cost monitoring, control, and optimization for LLM provider usage in the AI Presentation Intelligence Platform.

## Components

### 1. Cost Tracker (`cost_tracker.py`)

**Purpose**: Track token usage and calculate costs for every LLM call.

**Key Features**:
- Token usage extraction from LLM responses (supports multiple formats)
- Cost calculation based on provider-specific pricing
- Usage recording in `provider_usage` table
- Execution-level and tenant-level cost aggregation
- Provider usage statistics and analytics

**Usage**:
```python
from app.services.cost_tracker import CostTracker

tracker = CostTracker(db)
usage_record = await tracker.record_usage(
    execution_id=execution_id,
    provider_type=ProviderType.claude,
    response=llm_response,
)
```

### 2. Cost Controller (`cost_controller.py`)

**Purpose**: Enforce cost limits and prevent cost explosions.

**Key Features**:
- Maximum 4 LLM calls per request enforcement
- Configurable cost ceiling per execution (default: $0.50)
- Early stopping when quality improvements show diminishing returns (< 0.5 delta)
- Tenant-level daily cost thresholds (default: $10/day)
- Cost-per-quality-point efficiency metrics

**Usage**:
```python
from app.services.cost_controller import CostController

controller = CostController(db)
can_proceed, reason = await controller.check_and_enforce_limits(
    execution_id=execution_id,
    quality_scores=[7.0, 8.0, 8.3],
)
```

### 3. Provider Selector (`provider_selector.py`)

**Purpose**: Select the most cost-effective provider that meets quality requirements.

**Key Features**:
- Multi-factor provider scoring (health, cost, quality)
- Cost-based selection when multiple providers meet quality threshold
- Provider ranking and comparison
- Configurable scoring weights

**Scoring Algorithm**:
- Health Score (40%): Based on success rate and circuit breaker status
- Cost Score (40%): Lower cost = higher score
- Quality Score (20%): Historical quality performance

**Usage**:
```python
from app.services.provider_selector import ProviderSelector

selector = ProviderSelector(db)
provider = await selector.select_cost_optimal_provider(
    min_quality_threshold=8.0,
)
```

### 4. Cost Alert Service (`cost_alerts.py`)

**Purpose**: Send alerts when cost thresholds are reached.

**Key Features**:
- Webhook notifications at 80% and 100% thresholds
- Alert deduplication (once per day per alert type)
- Configurable webhook URLs per tenant
- Daily cost summaries
- Structured alert payloads with actionable recommendations

**Alert Types**:
- `threshold_80_percent`: Warning at 80% of daily limit
- `threshold_100_percent`: Critical at 100% of daily limit
- `daily_summary`: End-of-day cost summary
- `budget_exceeded`: Over-budget notification

**Usage**:
```python
from app.services.cost_alerts import CostAlertService

alert_service = CostAlertService(db)
await alert_service.send_threshold_alert(
    tenant_id=tenant_id,
    daily_cost=8.0,
    threshold=10.0,
    percent_used=80.0,
)
```

## Configuration

### Environment Variables

Add to `.env`:

```bash
# Cost Control
MAX_LLM_CALLS_PER_REQUEST=4
COST_CEILING_USD=0.50
TENANT_DAILY_COST_THRESHOLD_USD=10.0
COST_ALERT_WEBHOOK_URL=https://your-webhook-endpoint.com/alerts
```

### Provider Pricing

Default costs per 1K tokens (USD):

| Provider | Input | Output | Notes |
|----------|-------|--------|-------|
| Claude   | $0.003 | $0.015 | High quality, moderate cost |
| OpenAI   | $0.0025 | $0.010 | High quality, moderate cost |
| Groq     | $0.0001 | $0.0001 | Fast, very low cost |
| Local    | $0.00 | $0.00 | Free, variable quality |

Pricing can be overridden in the `provider_configs` table.

## Integration Example

```python
from app.services.cost_tracking_integration import CostAwareLLMService

# Initialize service
cost_service = CostAwareLLMService(db)

# Check tenant limits
can_proceed, daily_cost = await cost_service.check_and_alert_tenant_costs(
    tenant_id=tenant_id,
    threshold=10.0,
)

if not can_proceed:
    # Queue request for tomorrow
    return

# Select cost-optimal provider
provider = await cost_service.select_cost_optimal_provider(
    min_quality_threshold=8.0,
)

# Make LLM call with cost tracking
response, can_continue = await cost_service.call_llm_with_cost_tracking(
    execution_id=execution_id,
    provider_type=provider,
    prompt="Generate presentation...",
    quality_scores=[7.0, 8.0],
)

# Get cost summary
summary = await cost_service.get_execution_cost_summary(execution_id)
```

## Cost Control Flow

```
Request Start
    ↓
Check Tenant Daily Limit
    ↓ (if under limit)
Select Cost-Optimal Provider
    ↓
Check Execution Limits (calls & cost)
    ↓ (if allowed)
Make LLM Call
    ↓
Extract Token Usage
    ↓
Calculate Cost
    ↓
Record in provider_usage Table
    ↓
Check Quality Improvement
    ↓ (if < 0.5 delta)
Early Stop (Diminishing Returns)
    ↓ (else if under limits)
Continue Feedback Loop
    ↓ (else)
Deliver Best Result
```

## Database Schema

### provider_usage Table

```sql
CREATE TABLE provider_usage (
    id UUID PRIMARY KEY,
    execution_id UUID REFERENCES pipeline_executions(id),
    provider_id UUID REFERENCES provider_configs(id),
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    cost_usd FLOAT NOT NULL,
    created_at TIMESTAMP NOT NULL
);
```

## Monitoring and Analytics

### Execution-Level Metrics

```python
# Get cost summary for an execution
summary = await cost_controller.get_cost_summary(execution_id)
# Returns:
# {
#     "llm_call_count": 3,
#     "total_cost_usd": 0.35,
#     "cost_ceiling_usd": 0.50,
#     "remaining_calls": 1,
#     "remaining_budget_usd": 0.15,
#     "budget_used_percent": 70.0
# }
```

### Tenant-Level Metrics

```python
# Get tenant cost summary
summary = await tenant_controller.get_tenant_cost_summary(tenant_id)
# Returns:
# {
#     "daily_cost_usd": 8.5,
#     "daily_threshold_usd": 10.0,
#     "remaining_budget_usd": 1.5,
#     "budget_used_percent": 85.0,
#     "alert_triggered": true,
#     "limit_reached": false
# }
```

### Provider-Level Metrics

```python
# Get provider usage statistics
stats = await cost_tracker.get_provider_usage_stats(
    provider_type=ProviderType.claude,
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31),
)
# Returns:
# {
#     "call_count": 1250,
#     "total_prompt_tokens": 500000,
#     "total_completion_tokens": 250000,
#     "total_tokens": 750000,
#     "total_cost": 125.50,
#     "avg_cost_per_call": 0.10
# }
```

## Testing

Run tests:
```bash
poetry run pytest tests/test_cost_tracking.py -v
```

Test coverage includes:
- Token usage extraction from various response formats
- Cost calculation for all providers
- Cost limit enforcement (calls and budget)
- Early stopping logic
- Provider selection based on cost
- Alert webhook delivery
- Alert deduplication

## References

- **Requirements**: Req 11 (Provider Cost Tracking), Req 47 (Cost Control)
- **Design**: Cost Control Design section
- **Tasks**: Task 6 and all subtasks
