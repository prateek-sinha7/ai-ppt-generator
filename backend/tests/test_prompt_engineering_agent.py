"""
Tests for Prompt Engineering Agent.

Tests cover:
- Provider-specific prompt template selection
- Prompt optimization (structure, length, few-shot examples)
- Token limit validation
- Prompt regeneration for failover
- Prompt versioning
"""

import pytest
from app.agents.prompt_engineering import (
    PromptEngineeringAgent,
    PROMPT_TEMPLATES,
    PROVIDER_TOKEN_LIMITS,
    OptimizedPrompt,
)
from app.db.models import ProviderType


@pytest.fixture
def agent():
    """Create a PromptEngineeringAgent instance"""
    return PromptEngineeringAgent()


@pytest.fixture
def sample_research_findings():
    """Sample research findings for testing"""
    return {
        "sections": [
            "Executive Summary",
            "Market Analysis",
            "Risk Assessment",
            "Opportunities",
            "Recommendations",
            "Implementation Plan",
        ],
        "risks": [
            "Market volatility",
            "Regulatory changes",
            "Competition pressure",
        ],
        "opportunities": [
            "Digital transformation",
            "Market expansion",
            "Cost optimization",
        ],
        "terminology": [
            "ROI", "KPI", "market share", "competitive advantage", "value proposition"
        ],
        "context_summary": "Healthcare industry analysis focusing on digital transformation opportunities.",
    }


@pytest.fixture
def sample_presentation_plan():
    """Sample presentation plan for testing"""
    return {
        "total_slides": 10,
        "sections": [
            {
                "name": "Title",
                "slide_count": 1,
                "slide_types": ["title"],
            },
            {
                "name": "Agenda",
                "slide_count": 1,
                "slide_types": ["content"],
            },
            {
                "name": "Analysis",
                "slide_count": 5,
                "slide_types": ["content", "chart", "content", "table", "comparison"],
            },
            {
                "name": "Recommendations",
                "slide_count": 2,
                "slide_types": ["content", "content"],
            },
            {
                "name": "Conclusion",
                "slide_count": 1,
                "slide_types": ["content"],
            },
        ],
    }


@pytest.fixture
def sample_data_enrichment():
    """Sample data enrichment for testing"""
    return {
        "charts": [
            {
                "type": "bar",
                "data": [10, 20, 30, 40],
                "labels": ["Q1", "Q2", "Q3", "Q4"],
            }
        ],
        "tables": [
            {
                "headers": ["Metric", "Value"],
                "rows": [["Revenue", "$1M"], ["Growth", "25%"]],
            }
        ],
    }


class TestPromptTemplateSelection:
    """Test provider-specific prompt template selection"""
    
    def test_claude_template_exists(self):
        """Test Claude template is available"""
        assert ProviderType.claude in PROMPT_TEMPLATES
        template = PROMPT_TEMPLATES[ProviderType.claude]
        assert template.provider_type == ProviderType.claude
        assert "XML" in template.optimization_notes or "structured" in template.optimization_notes
    
    def test_openai_template_exists(self):
        """Test OpenAI template is available"""
        assert ProviderType.openai in PROMPT_TEMPLATES
        template = PROMPT_TEMPLATES[ProviderType.openai]
        assert template.provider_type == ProviderType.openai
        assert len(template.few_shot_examples) > 0
    
    def test_groq_template_exists(self):
        """Test Groq template is available"""
        assert ProviderType.groq in PROMPT_TEMPLATES
        template = PROMPT_TEMPLATES[ProviderType.groq]
        assert template.provider_type == ProviderType.groq
        assert "speed" in template.optimization_notes or "efficient" in template.optimization_notes
    
    def test_local_template_exists(self):
        """Test Local LLM template is available"""
        assert ProviderType.local in PROMPT_TEMPLATES
        template = PROMPT_TEMPLATES[ProviderType.local]
        assert template.provider_type == ProviderType.local
        assert "simple" in template.optimization_notes


class TestPromptGeneration:
    """Test prompt generation with optimization"""
    
    def test_generate_claude_prompt(
        self,
        agent,
        sample_research_findings,
        sample_presentation_plan,
        sample_data_enrichment,
    ):
        """Test generating optimized prompt for Claude"""
        prompt = agent.generate_prompt(
            provider_type=ProviderType.claude,
            topic="Healthcare Digital Transformation",
            industry="healthcare",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            data_enrichment=sample_data_enrichment,
            execution_id="test-exec-123",
        )
        
        assert isinstance(prompt, OptimizedPrompt)
        assert prompt.provider_type == ProviderType.claude
        assert prompt.version == "1.0.0"
        assert len(prompt.prompt_id) == 16
        assert "Healthcare Digital Transformation" in prompt.user_prompt
        assert "healthcare" in prompt.user_prompt
        assert prompt.estimated_tokens > 0
        assert prompt.estimated_tokens <= prompt.token_limit
    
    def test_generate_openai_prompt(
        self,
        agent,
        sample_research_findings,
        sample_presentation_plan,
    ):
        """Test generating optimized prompt for OpenAI"""
        prompt = agent.generate_prompt(
            provider_type=ProviderType.openai,
            topic="Financial Risk Assessment",
            industry="finance",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            execution_id="test-exec-456",
        )
        
        assert prompt.provider_type == ProviderType.openai
        assert "Financial Risk Assessment" in prompt.user_prompt
        assert prompt.estimated_tokens <= PROVIDER_TOKEN_LIMITS[ProviderType.openai]["recommended_prompt_tokens"]
    
    def test_generate_groq_prompt(
        self,
        agent,
        sample_research_findings,
        sample_presentation_plan,
    ):
        """Test generating optimized prompt for Groq"""
        prompt = agent.generate_prompt(
            provider_type=ProviderType.groq,
            topic="Retail Market Analysis",
            industry="retail",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            execution_id="test-exec-789",
        )
        
        assert prompt.provider_type == ProviderType.groq
        # Groq prompts should be more concise
        assert prompt.estimated_tokens <= PROVIDER_TOKEN_LIMITS[ProviderType.groq]["recommended_prompt_tokens"]
    
    def test_prompt_includes_all_context(
        self,
        agent,
        sample_research_findings,
        sample_presentation_plan,
        sample_data_enrichment,
    ):
        """Test prompt includes all required context"""
        prompt = agent.generate_prompt(
            provider_type=ProviderType.claude,
            topic="Test Topic",
            industry="technology",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            data_enrichment=sample_data_enrichment,
            execution_id="test-exec-context",
        )
        
        # Check research findings are included
        assert "Market Analysis" in prompt.user_prompt
        assert "Market volatility" in prompt.user_prompt
        
        # Check presentation plan is included
        assert "10" in prompt.user_prompt or "Total Slides" in prompt.user_prompt
        
        # Check data enrichment is included
        assert "Q1" in prompt.user_prompt or "Revenue" in prompt.user_prompt


class TestTokenLimitValidation:
    """Test token limit validation"""
    
    def test_validate_within_limit(self, agent):
        """Test validation passes when within limit"""
        prompt = OptimizedPrompt(
            prompt_id="test123",
            version="1.0.0",
            provider_type=ProviderType.claude,
            system_prompt="Test system prompt",
            user_prompt="Test user prompt",
            estimated_tokens=1000,
            token_limit=200000,
            metadata={},
            created_at="2024-01-01T00:00:00",
        )
        
        is_valid, error = agent.validate_token_limit(prompt)
        assert is_valid
        assert error is None
    
    def test_validate_exceeds_limit(self, agent):
        """Test validation fails when exceeding limit"""
        prompt = OptimizedPrompt(
            prompt_id="test456",
            version="1.0.0",
            provider_type=ProviderType.local,
            system_prompt="Test system prompt",
            user_prompt="Test user prompt",
            estimated_tokens=10000,
            token_limit=8192,
            metadata={},
            created_at="2024-01-01T00:00:00",
        )
        
        is_valid, error = agent.validate_token_limit(prompt)
        assert not is_valid
        assert error is not None
        assert "exceeds token limit" in error
    
    def test_truncation_for_large_prompts(
        self,
        agent,
        sample_research_findings,
        sample_presentation_plan,
    ):
        """Test that prompts are kept within the recommended token limit."""
        # Create very large data enrichment
        large_data = {
            "charts": [{"data": list(range(1000)), "title": f"Chart {i}", "type": "bar"} for i in range(100)],
            "tables": [{"rows": [["x" * 50, "y" * 50] for _ in range(1000)], "title": f"Table {i}"} for i in range(100)],
        }

        prompt = agent.generate_prompt(
            provider_type=ProviderType.groq,
            topic="Test Topic",
            industry="technology",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            data_enrichment=large_data,
            execution_id="test-exec-truncate",
        )

        # The prompt must always fit within the recommended token limit
        assert prompt.estimated_tokens <= PROVIDER_TOKEN_LIMITS[ProviderType.groq]["recommended_prompt_tokens"]
        # truncated flag reflects whether the raw data exceeded the limit before capping
        assert isinstance(prompt.metadata.get("truncated"), bool)


class TestPromptFailover:
    """Test prompt regeneration for failover"""
    
    def test_regenerate_for_failover(
        self,
        agent,
        sample_research_findings,
        sample_presentation_plan,
    ):
        """Test regenerating prompt for different provider"""
        # Generate original prompt for Claude
        original = agent.generate_prompt(
            provider_type=ProviderType.claude,
            topic="Test Topic",
            industry="healthcare",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            execution_id="test-exec-original",
        )
        
        # Regenerate for OpenAI failover
        failover = agent.regenerate_for_failover(
            original_prompt=original,
            new_provider_type=ProviderType.openai,
            topic="Test Topic",
            industry="healthcare",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            execution_id="test-exec-failover",
        )
        
        assert failover.provider_type == ProviderType.openai
        assert failover.prompt_id != original.prompt_id
        assert failover.version == original.version
        # Content should be similar but optimized for different provider
        assert "Test Topic" in failover.user_prompt
    
    def test_failover_maintains_context(
        self,
        agent,
        sample_research_findings,
        sample_presentation_plan,
    ):
        """Test failover prompt maintains all context"""
        original = agent.generate_prompt(
            provider_type=ProviderType.claude,
            topic="Healthcare Analysis",
            industry="healthcare",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            execution_id="test-exec-context-1",
        )
        
        failover = agent.regenerate_for_failover(
            original_prompt=original,
            new_provider_type=ProviderType.groq,
            topic="Healthcare Analysis",
            industry="healthcare",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            execution_id="test-exec-context-2",
        )
        
        # Both should contain key context
        assert "Healthcare Analysis" in original.user_prompt
        assert "Healthcare Analysis" in failover.user_prompt
        assert "healthcare" in original.user_prompt
        assert "healthcare" in failover.user_prompt


class TestPromptVersioning:
    """Test prompt versioning"""
    
    def test_prompt_has_version(
        self,
        agent,
        sample_research_findings,
        sample_presentation_plan,
    ):
        """Test generated prompt includes version"""
        prompt = agent.generate_prompt(
            provider_type=ProviderType.claude,
            topic="Test Topic",
            industry="technology",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            execution_id="test-exec-version",
        )
        
        assert prompt.version == "1.0.0"
    
    def test_prompt_has_unique_id(
        self,
        agent,
        sample_research_findings,
        sample_presentation_plan,
    ):
        """Test each prompt has unique ID"""
        prompt1 = agent.generate_prompt(
            provider_type=ProviderType.claude,
            topic="Topic 1",
            industry="healthcare",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            execution_id="test-exec-id-1",
        )
        
        prompt2 = agent.generate_prompt(
            provider_type=ProviderType.claude,
            topic="Topic 2",
            industry="finance",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            execution_id="test-exec-id-2",
        )
        
        assert prompt1.prompt_id != prompt2.prompt_id
    
    def test_prompt_metadata_includes_execution_id(
        self,
        agent,
        sample_research_findings,
        sample_presentation_plan,
    ):
        """Test prompt metadata includes execution ID"""
        execution_id = "test-exec-metadata-123"
        
        prompt = agent.generate_prompt(
            provider_type=ProviderType.openai,
            topic="Test Topic",
            industry="retail",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            execution_id=execution_id,
        )
        
        assert prompt.metadata["execution_id"] == execution_id
        assert prompt.metadata["topic"] == "Test Topic"
        assert prompt.metadata["industry"] == "retail"
    
    def test_prompt_to_dict(
        self,
        agent,
        sample_research_findings,
        sample_presentation_plan,
    ):
        """Test prompt can be serialized to dict"""
        prompt = agent.generate_prompt(
            provider_type=ProviderType.claude,
            topic="Test Topic",
            industry="technology",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan,
            execution_id="test-exec-dict",
        )
        
        prompt_dict = prompt.to_dict()
        
        assert isinstance(prompt_dict, dict)
        assert prompt_dict["prompt_id"] == prompt.prompt_id
        assert prompt_dict["version"] == prompt.version
        assert prompt_dict["provider_type"] == ProviderType.claude
        assert "metadata" in prompt_dict


class TestTokenEstimation:
    """Test token estimation"""
    
    def test_estimate_tokens(self, agent):
        """Test token estimation heuristic"""
        text = "This is a test sentence with approximately twenty characters per word."
        estimated = agent._estimate_tokens(text)
        
        # Should be roughly text length / 4
        assert estimated > 0
        assert estimated == len(text) // 4
    
    def test_truncate_to_token_limit(self, agent):
        """Test text truncation to token limit"""
        long_text = "word " * 1000  # 5000 characters
        max_tokens = 100  # ~400 characters
        
        truncated = agent._truncate_to_token_limit(long_text, max_tokens)
        
        assert len(truncated) <= max_tokens * 4 + 3  # +3 for "..."
        assert "..." in truncated
