# AI Agents

This directory contains the AI agents for the Presentation Intelligence Platform.

## Industry Classifier Agent

The Industry Classifier Agent is the **first agent** in the pipeline. It automatically detects the industry from a user-provided topic using a three-step classification approach.

### Features

1. **Keyword Matching (Step 1)**: Fast, deterministic matching against industry seed term dictionaries
2. **Semantic Similarity (Step 2)**: Embedding-based similarity scoring using sentence-transformers
3. **LLM Classification (Step 3)**: Open-ended LLM-based classification for any industry not matched by previous steps
4. **Audience Inference**: Automatically infers target audience (executives/analysts/technical/general) from topic language
5. **Template Selection**: Maps detected industry + sub-sector to best-fit presentation template
6. **Theme Selection**: Selects appropriate theme (McKinsey/Deloitte/Dark Modern) based on industry and audience

### Usage

```python
from app.agents.industry_classifier import industry_classifier

# Classify a topic
topic = "Clinical trial results for new pharmaceutical treatment"
execution_id = "unique-execution-id"

context = await industry_classifier.classify(topic, execution_id)

print(f"Industry: {context.industry}")
print(f"Confidence: {context.confidence}")
print(f"Audience: {context.target_audience}")
print(f"Template: {context.selected_template_name}")
print(f"Theme: {context.theme}")
print(f"Method: {context.classification_method}")
```

### Using the Service Layer

For database integration, use the `IndustryClassifierService`:

```python
from app.services.industry_classifier_service import industry_classifier_service
from app.db.session import get_db

async with get_db() as db:
    context = await industry_classifier_service.classify_and_store(
        db=db,
        presentation_id=presentation_id,
        topic=topic,
        execution_id=execution_id,
    )
```

This will:
1. Run the classification
2. Resolve the template ID from the database
3. Store all detected context on the presentation record

### Classification Methods

The agent uses three classification methods in sequence:

1. **keyword**: Fast keyword matching (threshold: 0.6)
2. **semantic**: Semantic similarity using embeddings (threshold: 0.8)
3. **llm**: LLM-based open-ended classification (fallback for any industry)

### Supported Industries

The agent includes seed terms for common industries:
- Healthcare
- Insurance
- Automobile
- Finance
- Technology
- Retail
- Education
- Manufacturing
- Logistics
- Real Estate

**Note**: The agent is not limited to these industries. The LLM classification step can identify **any industry** from the topic text.

### Output Schema

```python
@dataclass
class DetectedContext:
    industry: str                      # Detected industry
    confidence: float                  # Confidence score (0.0-1.0)
    sub_sector: Optional[str]          # Specific sub-sector
    target_audience: str               # executives/analysts/technical/general
    selected_template_id: Optional[str] # Template UUID
    selected_template_name: str        # Template name
    theme: str                         # mckinsey/deloitte/dark_modern
    compliance_context: List[str]      # Relevant compliance frameworks
    classification_method: str         # keyword/semantic/llm
```

### Database Storage

The detected context is stored on the `presentations` table:

- `detected_industry`
- `detection_confidence`
- `detected_sub_sector`
- `inferred_audience`
- `selected_template_id`
- `selected_theme`
- `compliance_context` (JSONB)

### Testing

Run tests with:

```bash
poetry run pytest tests/test_industry_classifier.py -v
```

### Performance

- Keyword matching: < 10ms
- Semantic similarity: < 100ms (with pre-computed centroids)
- LLM classification: 1-3 seconds (only when needed)
- Total classification time: Typically < 200ms for keyword/semantic matches
