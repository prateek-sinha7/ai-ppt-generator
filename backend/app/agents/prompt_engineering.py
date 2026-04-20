"""
Prompt Engineering Agent - Multi-LLM provider prompt optimization.

This agent generates and optimizes prompts for different LLM providers:
- Provider-specific prompt templates (Claude, OpenAI, Groq, Local LLM)
- Prompt structure, length, and few-shot example optimization
- Token limit validation per provider
- Prompt regeneration during provider failover
- Prompt versioning with metadata tracking

The agent ensures each provider receives optimally formatted prompts
for generating structured Slide_JSON presentations.
"""

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import structlog

from pydantic import BaseModel, Field

from app.db.models import ProviderType


logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Provider Token Limits
# ---------------------------------------------------------------------------

PROVIDER_TOKEN_LIMITS = {
    ProviderType.claude: {
        "max_input_tokens": 200000,  # Claude 3.5 Sonnet
        "max_output_tokens": 8192,
        "recommended_prompt_tokens": 8000,  # Leave room for context
    },
    ProviderType.openai: {
        "max_input_tokens": 128000,  # GPT-4o
        "max_output_tokens": 16384,
        "recommended_prompt_tokens": 6000,
    },
    ProviderType.groq: {
        "max_input_tokens": 32768,  # Groq Llama models
        "max_output_tokens": 8192,
        "recommended_prompt_tokens": 4000,
    },
    ProviderType.local: {
        "max_input_tokens": 8192,  # Conservative default for local models
        "max_output_tokens": 4096,
        "recommended_prompt_tokens": 2000,
    },
}


# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------

class PromptTemplate(BaseModel):
    """Base prompt template structure"""
    provider_type: ProviderType
    system_prompt: str
    user_prompt_template: str
    few_shot_examples: List[Dict[str, str]] = Field(default_factory=list)
    json_schema_instructions: str
    optimization_notes: str


# Claude-specific template (verbose, structured, XML-friendly)
CLAUDE_TEMPLATE = PromptTemplate(
    provider_type=ProviderType.claude,
    system_prompt="""You are an expert presentation designer specializing in creating professional, consulting-grade slide decks.

Your task is to generate a complete presentation following a predefined structure plan. You will receive:
1. A presentation topic
2. Detected industry context
3. Research findings with business insights
4. A detailed presentation plan specifying exact slide count, types, and sections
5. Data enrichment with realistic business metrics, charts, and tables

<instructions>
You MUST follow the presentation plan exactly:
- Generate the exact number of slides specified
- Use the exact slide types specified for each position
- Follow the section structure provided
- Maintain consulting storytelling flow (Title → Agenda → Problem → Analysis → Evidence → Recommendations → Conclusion)

Content constraints:
- Titles: Maximum 8 words, clear and impactful
- Bullets: Maximum 4 bullets per slide, 6-8 words each
- No long paragraphs - use concise, actionable language
- Ensure visual diversity - no more than 2 consecutive slides of the same type

CRITICAL - Visual data requirements:
- For "chart" type slides: You MUST populate content.chart_data as an array of {label, value} objects using REAL numbers from the data_enrichment section. Set content.chart_type to "bar", "line", or "pie". Use the REAL labels from data_enrichment (e.g. "Primary Care", "Q1 2023", "North America") — NOT generic "Category 1, 2, 3". Add content.highlight_text with a key insight.
- For "table" type slides: You MUST populate content.table_data with {headers: [...], rows: [[...]]} using REAL data from data_enrichment. Add content.highlight_text with a key insight.
- For "comparison" type slides: You MUST populate content.comparison_data with {left_column: {heading, bullets}, right_column: {heading, bullets}}. Add content.highlight_text summarizing the key difference.
- For "content" type slides: Add content.icon_name (choose from: TrendingUp, TrendingDown, Users, Shield, Zap, Target, Award, BarChart2, Globe, Layers, AlertTriangle, CheckCircle, DollarSign, Activity, Briefcase) and content.highlight_text with a key takeaway.
- For "metric" type slides: Populate content.metric_value (e.g. "$847B"), content.metric_label (e.g. "Global Market Size"), content.metric_trend (e.g. "+12.3% YoY"), content.bullets with 3 context points, content.icon_name.
- ALWAYS include speaker_notes for every slide (2-3 sentences for the presenter).
- NEVER leave chart_data, table_data, or comparison_data empty — always fill with actual data values.
- ALWAYS include icon_name and highlight_text for visual richness.

Visual hints:
- "centered" for title slides
- "bullet-left" for content slides
- "split-chart-right" for chart slides
- "split-table-left" for table slides
- "two-column" for comparison slides
- "highlight-metric" for metric slides
</instructions>

Return your response as valid JSON conforming to the Slide_JSON schema.""",
    user_prompt_template="""<topic>{topic}</topic>

<industry>{industry}</industry>

<research_findings>
{research_findings}
</research_findings>

<presentation_plan>
{presentation_plan}
</presentation_plan>

<data_enrichment>
{data_enrichment}
</data_enrichment>

Generate a complete presentation following the plan exactly. Return valid JSON only.""",
    few_shot_examples=[],  # Claude works well without few-shot examples
    json_schema_instructions="""
Return JSON with this structure. IMPORTANT: For chart/table/comparison slides, you MUST populate the data fields using the data from <data_enrichment>:

{
  "schema_version": "1.0.0",
  "presentation_id": "string",
  "total_slides": number,
  "slides": [
    {
      "slide_id": "string",
      "slide_number": number,
      "type": "title",
      "title": "string (max 8 words)",
      "content": { "subtitle": "string" },
      "visual_hint": "centered"
    },
    {
      "slide_id": "string",
      "slide_number": number,
      "type": "content",
      "title": "string (max 8 words)",
      "content": {
        "bullets": ["bullet 1 (6-8 words)", "bullet 2", "bullet 3", "bullet 4"],
        "icon_name": "TrendingUp",
        "highlight_text": "Key insight or takeaway in one sentence"
      },
      "visual_hint": "bullet-left"
    },
    {
      "slide_id": "string",
      "slide_number": number,
      "type": "chart",
      "title": "string (max 8 words)",
      "content": {
        "chart_type": "bar",
        "chart_data": [
          {"label": "Category A", "value": 42.5},
          {"label": "Category B", "value": 67.3},
          {"label": "Category C", "value": 55.1},
          {"label": "Category D", "value": 78.9},
          {"label": "Category E", "value": 61.2}
        ],
        "highlight_text": "Key insight about the chart"
      },
      "visual_hint": "split-chart-right"
    },
    {
      "slide_id": "string",
      "slide_number": number,
      "type": "table",
      "title": "string (max 8 words)",
      "content": {
        "table_data": {
          "headers": ["Metric", "Value", "Trend"],
          "rows": [
            ["Revenue Growth", "12.5%", "↑"],
            ["Market Share", "23.4%", "↑"],
            ["Cost Reduction", "8.2%", "↓"]
          ]
        },
        "highlight_text": "Key insight about the table"
      },
      "visual_hint": "split-table-left"
    },
    {
      "slide_id": "string",
      "slide_number": number,
      "type": "comparison",
      "title": "string (max 8 words)",
      "content": {
        "comparison_data": {
          "left_column": {
            "heading": "Current State",
            "bullets": ["Point 1", "Point 2", "Point 3"]
          },
          "right_column": {
            "heading": "Future State",
            "bullets": ["Point 1", "Point 2", "Point 3"]
          }
        }
      },
      "visual_hint": "two-column"
    }
  ]
}

CRITICAL RULES:
- "title" MUST be at the slide root level (NOT inside content) — e.g. {"slide_id": "1", "title": "My Title", "content": {...}}
- NEVER put title inside content — it belongs at the slide root
- chart slides MUST have chart_data as an array of {label, value} objects with REAL numbers from the data_enrichment
- Use REAL labels from data_enrichment (industry segments, time periods, regions) — NOT "Category 1, 2, 3"
- table slides MUST have table_data with headers array and rows array of arrays
- comparison slides MUST have comparison_data with left_column and right_column objects
- metric slides MUST have metric_value, metric_label, metric_trend in content
- EVERY slide MUST have speaker_notes (2-3 sentences)
- chart_type must be one of: "bar", "line", "pie"
- icon_name must be a valid Lucide icon name
""",
    optimization_notes="Claude excels with structured XML-style input and detailed instructions. Use clear hierarchical formatting."
)


# OpenAI-specific template (concise, direct, JSON-focused)
OPENAI_TEMPLATE = PromptTemplate(
    provider_type=ProviderType.openai,
    system_prompt="""You are an expert presentation designer creating professional slide decks.

Generate a complete presentation following the provided structure plan exactly.

Key requirements:
- Follow the presentation plan: exact slide count, types, and sections
- Titles: max 8 words
- Bullets: max 4 per slide, 6-8 words each
- Consulting storytelling structure: Title → Agenda → Problem → Analysis → Evidence → Recommendations → Conclusion
- Visual diversity: no more than 2 consecutive slides of same type

CRITICAL - Visual data requirements:
- chart slides: MUST have content.chart_data as [{label, value}] array with REAL numbers from data enrichment. Set content.chart_type to "bar", "line", or "pie".
- table slides: MUST have content.table_data as {headers: [...], rows: [[...]]} with REAL data.
- comparison slides: MUST have content.comparison_data with left_column and right_column objects.
- NEVER leave these fields empty — always populate with actual data values.

Visual hints:
- "centered" (title slides)
- "bullet-left" (content slides)
- "split-chart-right" (chart slides)
- "split-table-left" (table slides)
- "two-column" (comparison slides)
- "highlight-metric" (metric slides)

Return valid JSON conforming to Slide_JSON schema.""",
    user_prompt_template="""Topic: {topic}

Industry: {industry}

Research Findings:
{research_findings}

Presentation Plan:
{presentation_plan}

Data Enrichment:
{data_enrichment}

Generate the complete presentation as JSON following the plan exactly.""",
    few_shot_examples=[
        {
            "input": "Topic: Healthcare Digital Transformation",
            "output": '{"schema_version": "1.0.0", "total_slides": 7, "slides": [{"slide_id": "1", "slide_number": 1, "type": "title", "title": "Healthcare Digital Transformation", "content": {}, "visual_hint": "centered"}]}'
        }
    ],
    json_schema_instructions="""
JSON structure:
{
  "schema_version": "1.0.0",
  "total_slides": number,
  "slides": [
    {
      "slide_id": "string",
      "slide_number": number,
      "type": "title|content|chart|table|comparison",
      "title": "string",
      "content": {"bullets": [], "chart_data": {}, "table_data": {}},
      "visual_hint": "centered|bullet-left|split-chart-right|split-table-left|two-column|highlight-metric"
    }
  ]
}""",
    optimization_notes="OpenAI models prefer concise, direct instructions with clear JSON examples."
)


# Groq-specific template (fast, efficient, minimal)
GROQ_TEMPLATE = PromptTemplate(
    provider_type=ProviderType.groq,
    system_prompt="""You are a presentation designer. Generate professional slide decks following the provided plan.

Requirements:
- Follow presentation plan exactly (slide count, types, sections)
- Titles: max 8 words
- Bullets: max 4, 6-8 words each
- Structure: Title → Agenda → Problem → Analysis → Evidence → Recommendations → Conclusion
- Visual hints: centered, bullet-left, split-chart-right, split-table-left, two-column, highlight-metric

CRITICAL - You MUST populate visual data fields:
- chart slides: content.chart_data MUST be [{label, value}] array with real numbers. content.chart_type must be "bar", "line", or "pie".
- table slides: content.table_data MUST be {headers: [...], rows: [[...]]} with real data.
- comparison slides: content.comparison_data MUST have left_column and right_column with heading and bullets.
- Use actual metric values from the Data section provided.

Return valid JSON.""",
    user_prompt_template="""Topic: {topic}
Industry: {industry}

Research:
{research_findings}

Plan:
{presentation_plan}

Data:
{data_enrichment}

Generate presentation JSON following the plan.""",
    few_shot_examples=[],
    json_schema_instructions="""
JSON format:
{
  "schema_version": "1.0.0",
  "total_slides": number,
  "slides": [
    {
      "slide_id": "string",
      "slide_number": number,
      "type": "title|content|chart|table|comparison",
      "title": "string",
      "content": {
        "bullets": ["bullet 1", "bullet 2"],
        "chart_type": "bar|line|pie",
        "chart_data": [{"label": "Category A", "value": 42.5}, {"label": "Category B", "value": 67.3}],
        "table_data": {"headers": ["Col1", "Col2"], "rows": [["val1", "val2"]]},
        "comparison_data": {"left_column": {"heading": "Option A", "bullets": ["point 1"]}, "right_column": {"heading": "Option B", "bullets": ["point 1"]}},
        "highlight_text": "optional insight"
      },
      "visual_hint": "centered|bullet-left|split-chart-right|split-table-left|two-column|highlight-metric"
    }
  ]
}
IMPORTANT: chart_data, table_data, comparison_data MUST be populated with real values for their respective slide types.""",
    optimization_notes="Groq optimized for speed. Use minimal, efficient prompts with clear structure."
)


# Local LLM template (simple, forgiving, basic)
LOCAL_TEMPLATE = PromptTemplate(
    provider_type=ProviderType.local,
    system_prompt="""You are a presentation designer. Create a slide deck following the plan.

Rules:
- Follow the plan: slide count, types, sections
- Titles: max 8 words
- Bullets: max 4, short
- Return JSON

Visual hints: centered, bullet-left, split-chart-right, split-table-left, two-column, highlight-metric""",
    user_prompt_template="""Topic: {topic}
Industry: {industry}

Plan:
{presentation_plan}

Generate presentation JSON.""",
    few_shot_examples=[
        {
            "input": "Topic: Sales Strategy",
            "output": '{"schema_version": "1.0.0", "total_slides": 5, "slides": [{"slide_id": "1", "type": "title", "title": "Sales Strategy", "visual_hint": "centered"}]}'
        }
    ],
    json_schema_instructions="""
JSON:
{
  "schema_version": "1.0.0",
  "total_slides": number,
  "slides": [{"slide_id": "string", "type": "title|content|chart|table|comparison", "title": "string", "visual_hint": "string"}]
}""",
    optimization_notes="Local models may have limited capabilities. Use simple, clear instructions."
)


# Template registry
PROMPT_TEMPLATES: Dict[ProviderType, PromptTemplate] = {
    ProviderType.claude: CLAUDE_TEMPLATE,
    ProviderType.openai: OPENAI_TEMPLATE,
    ProviderType.groq: GROQ_TEMPLATE,
    ProviderType.local: LOCAL_TEMPLATE,
}


# ---------------------------------------------------------------------------
# Optimized Prompt Output
# ---------------------------------------------------------------------------

@dataclass
class OptimizedPrompt:
    """Optimized prompt ready for LLM provider"""
    prompt_id: str
    version: str
    provider_type: ProviderType
    system_prompt: str
    user_prompt: str
    estimated_tokens: int
    token_limit: int
    metadata: Dict[str, Any]
    created_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return asdict(self)


# ---------------------------------------------------------------------------
# Prompt Engineering Agent
# ---------------------------------------------------------------------------

class PromptEngineeringAgent:
    """
    Prompt Engineering Agent - Multi-LLM provider prompt optimization.
    
    Key responsibilities:
    1. Select provider-specific prompt template
    2. Optimize prompt structure, length, and examples
    3. Validate token limits
    4. Generate prompts for failover scenarios
    5. Version prompts with metadata
    """
    
    # Current prompt version
    PROMPT_VERSION = "1.0.0"
    
    def __init__(self):
        """Initialize the Prompt Engineering Agent"""
        pass
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Uses simple heuristic: ~4 characters per token (conservative estimate).
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
    
    def _truncate_to_token_limit(
        self,
        text: str,
        max_tokens: int,
        preserve_suffix: bool = True
    ) -> str:
        """
        Truncate text to fit within token limit.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum token count
            preserve_suffix: If True, preserve end of text; otherwise preserve beginning
            
        Returns:
            Truncated text
        """
        estimated_tokens = self._estimate_tokens(text)
        
        if estimated_tokens <= max_tokens:
            return text
        
        # Calculate character limit
        char_limit = max_tokens * 4
        
        if preserve_suffix:
            # Keep the end (more important for context)
            return "..." + text[-char_limit:]
        else:
            # Keep the beginning
            return text[:char_limit] + "..."
    
    def _format_research_findings(self, research_findings: Dict[str, Any]) -> str:
        """
        Format research findings for prompt inclusion.
        
        Args:
            research_findings: Research agent output
            
        Returns:
            Formatted string
        """
        sections = research_findings.get("sections", [])
        risks = research_findings.get("risks", [])
        opportunities = research_findings.get("opportunities", [])
        terminology = research_findings.get("terminology", [])
        context = research_findings.get("context_summary", "")
        
        formatted = f"""Context: {context}

Sections: {', '.join(sections)}

Key Risks:
{chr(10).join(f'- {risk}' for risk in risks)}

Key Opportunities:
{chr(10).join(f'- {opp}' for opp in opportunities)}

Domain Terminology: {', '.join(terminology)}"""
        
        return formatted
    
    def _format_presentation_plan(self, presentation_plan: Dict[str, Any]) -> str:
        """
        Format presentation plan for prompt inclusion.
        
        Args:
            presentation_plan: Storyboarding agent output
            
        Returns:
            Formatted string
        """
        total_slides = presentation_plan.get("total_slides", 0)
        sections = presentation_plan.get("sections", [])
        
        formatted = f"Total Slides: {total_slides}\n\nSection Structure:\n"
        
        for section in sections:
            name = section.get("name", "Unknown")
            slide_count = section.get("slide_count", 0)
            slide_types = section.get("slide_types", [])
            
            formatted += f"\n{name} ({slide_count} slides):\n"
            for i, slide_type in enumerate(slide_types, 1):
                formatted += f"  {i}. {slide_type}\n"
        
        return formatted
    
    def _format_data_enrichment(self, data_enrichment: Dict[str, Any]) -> str:
        """
        Format data enrichment for prompt inclusion.
        Formats charts and tables in a clear, LLM-friendly way so the LLM
        can directly use the values in chart_data and table_data fields.
        """
        if not data_enrichment:
            return "No enrichment data available."

        lines = []

        # Key metrics
        key_metrics = data_enrichment.get("key_metrics", {})
        if key_metrics:
            lines.append("KEY METRICS (use these values in chart_data and table_data):")
            for name, value in list(key_metrics.items())[:10]:
                lines.append(f"  - {name.replace('_', ' ').title()}: {value}")

        # Charts
        charts = data_enrichment.get("charts", [])
        if charts:
            lines.append("\nCHART DATA (use these directly in chart slides):")
            for i, chart in enumerate(charts[:4]):
                lines.append(f"\n  Chart {i+1}: {chart.get('title', 'Chart')}")
                lines.append(f"  Suggested type: {chart.get('chart_type', 'bar')}")
                labels = chart.get("labels", [])
                datasets = chart.get("datasets", [])
                if datasets and labels:
                    data_values = datasets[0].get("data", [])
                    lines.append(f"  chart_data: [")
                    for label, val in zip(labels, data_values):
                        lines.append(f'    {{"label": "{label}", "value": {round(val, 1)}}},')
                    lines.append(f"  ]")

        # Tables
        tables = data_enrichment.get("tables", [])
        if tables:
            lines.append("\nTABLE DATA (use these directly in table slides):")
            for i, table in enumerate(tables[:2]):
                lines.append(f"\n  Table {i+1}: {table.get('title', 'Table')}")
                headers = table.get("headers", [])
                rows = table.get("rows", [])
                lines.append(f"  headers: {headers}")
                lines.append(f"  rows: {rows[:6]}")

        return "\n".join(lines)
    
    def generate_prompt(
        self,
        provider_type: ProviderType,
        topic: str,
        industry: str,
        research_findings: Dict[str, Any],
        presentation_plan: Dict[str, Any],
        data_enrichment: Optional[Dict[str, Any]] = None,
        execution_id: str = "",
    ) -> OptimizedPrompt:
        """
        Generate optimized prompt for specified provider.
        
        Args:
            provider_type: Target LLM provider
            topic: Presentation topic
            industry: Detected industry
            research_findings: Research agent output
            presentation_plan: Storyboarding agent output
            data_enrichment: Optional data enrichment output
            execution_id: Execution ID for tracking
            
        Returns:
            OptimizedPrompt ready for provider
        """
        logger.info(
            "generating_prompt",
            provider_type=provider_type.value,
            topic=topic[:100],
            execution_id=execution_id,
        )
        
        # Get provider template
        template = PROMPT_TEMPLATES.get(provider_type, LOCAL_TEMPLATE)
        
        # Get token limits
        limits = PROVIDER_TOKEN_LIMITS.get(provider_type, PROVIDER_TOKEN_LIMITS[ProviderType.local])
        recommended_tokens = limits["recommended_prompt_tokens"]
        
        # Format context sections
        research_str = self._format_research_findings(research_findings)
        plan_str = self._format_presentation_plan(presentation_plan)
        data_str = self._format_data_enrichment(data_enrichment or {})
        
        # Build user prompt
        user_prompt = template.user_prompt_template.format(
            topic=topic,
            industry=industry,
            research_findings=research_str,
            presentation_plan=plan_str,
            data_enrichment=data_str,
        )
        
        # Estimate tokens
        system_tokens = self._estimate_tokens(template.system_prompt)
        user_tokens = self._estimate_tokens(user_prompt)
        total_tokens = system_tokens + user_tokens
        
        # Truncate if needed
        if total_tokens > recommended_tokens:
            logger.warning(
                "prompt_exceeds_recommended_tokens",
                total_tokens=total_tokens,
                recommended_tokens=recommended_tokens,
                provider_type=provider_type.value,
            )
            
            # Truncate data enrichment first (least critical)
            available_tokens = recommended_tokens - system_tokens - self._estimate_tokens(
                template.user_prompt_template.format(
                    topic=topic,
                    industry=industry,
                    research_findings=research_str,
                    presentation_plan=plan_str,
                    data_enrichment="",
                )
            )
            
            if available_tokens > 0:
                data_str = self._truncate_to_token_limit(data_str, available_tokens)
            else:
                data_str = ""
            
            # Rebuild user prompt
            user_prompt = template.user_prompt_template.format(
                topic=topic,
                industry=industry,
                research_findings=research_str,
                presentation_plan=plan_str,
                data_enrichment=data_str,
            )
            
            total_tokens = system_tokens + self._estimate_tokens(user_prompt)
        
        # Generate prompt ID
        prompt_content = f"{template.system_prompt}|{user_prompt}"
        prompt_id = hashlib.sha256(prompt_content.encode()).hexdigest()[:16]
        
        # Create optimized prompt
        optimized = OptimizedPrompt(
            prompt_id=prompt_id,
            version=self.PROMPT_VERSION,
            provider_type=provider_type,
            system_prompt=template.system_prompt,
            user_prompt=user_prompt,
            estimated_tokens=total_tokens,
            token_limit=limits["max_input_tokens"],
            metadata={
                "topic": topic,
                "industry": industry,
                "execution_id": execution_id,
                "template_optimization_notes": template.optimization_notes,
                "truncated": total_tokens > recommended_tokens,
            },
            created_at=datetime.utcnow().isoformat(),
        )
        
        logger.info(
            "prompt_generated",
            prompt_id=prompt_id,
            provider_type=provider_type.value,
            estimated_tokens=total_tokens,
            execution_id=execution_id,
        )
        
        return optimized
    
    def regenerate_for_failover(
        self,
        original_prompt: OptimizedPrompt,
        new_provider_type: ProviderType,
        topic: str,
        industry: str,
        research_findings: Dict[str, Any],
        presentation_plan: Dict[str, Any],
        data_enrichment: Optional[Dict[str, Any]] = None,
        execution_id: str = "",
    ) -> OptimizedPrompt:
        """
        Regenerate prompt for failover to different provider.
        
        Args:
            original_prompt: Original prompt that failed
            new_provider_type: New provider to target
            topic: Presentation topic
            industry: Detected industry
            research_findings: Research agent output
            presentation_plan: Storyboarding agent output
            data_enrichment: Optional data enrichment output
            execution_id: Execution ID for tracking
            
        Returns:
            New OptimizedPrompt for failover provider
        """
        logger.info(
            "regenerating_prompt_for_failover",
            original_provider=original_prompt.provider_type.value,
            new_provider=new_provider_type.value,
            execution_id=execution_id,
        )
        
        # Generate new prompt for failover provider
        return self.generate_prompt(
            provider_type=new_provider_type,
            topic=topic,
            industry=industry,
            research_findings=research_findings,
            presentation_plan=presentation_plan,
            data_enrichment=data_enrichment,
            execution_id=execution_id,
        )
    
    def validate_token_limit(
        self,
        prompt: OptimizedPrompt,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate prompt is within provider token limits.
        
        Args:
            prompt: Optimized prompt to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if prompt.estimated_tokens > prompt.token_limit:
            error = (
                f"Prompt exceeds token limit: {prompt.estimated_tokens} > {prompt.token_limit} "
                f"for provider {prompt.provider_type.value}"
            )
            logger.error(
                "prompt_token_limit_exceeded",
                estimated_tokens=prompt.estimated_tokens,
                token_limit=prompt.token_limit,
                provider_type=prompt.provider_type.value,
            )
            return False, error
        
        return True, None


# Global agent instance
prompt_engineering_agent = PromptEngineeringAgent()
