"""
Example usage of Prompt Engineering Agent in the pipeline.

This demonstrates how the Prompt Engineering Agent integrates with:
- Research Agent output
- Storyboarding Agent output
- Data Enrichment Agent output
- LLM Provider Service
- Pipeline execution tracking
"""

import asyncio
from datetime import datetime
from uuid import uuid4

from app.agents.prompt_engineering import prompt_engineering_agent
from app.db.models import ProviderType


async def example_prompt_generation():
    """
    Example: Generate optimized prompt for Claude provider
    """
    print("=" * 80)
    print("Example 1: Generate Optimized Prompt for Claude")
    print("=" * 80)
    
    # Simulated research findings from Research Agent
    research_findings = {
        "sections": [
            "Executive Summary",
            "Market Overview",
            "Risk Assessment",
            "Strategic Opportunities",
            "Implementation Roadmap",
            "Financial Projections",
        ],
        "risks": [
            "Regulatory compliance challenges",
            "Market competition intensity",
            "Technology adoption barriers",
        ],
        "opportunities": [
            "Digital transformation potential",
            "Market expansion opportunities",
            "Operational efficiency gains",
        ],
        "terminology": [
            "ROI", "KPI", "digital transformation", "market penetration", "value chain"
        ],
        "context_summary": "Healthcare industry analysis focusing on digital health transformation and regulatory compliance.",
    }
    
    # Simulated presentation plan from Storyboarding Agent
    presentation_plan = {
        "total_slides": 12,
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
                "name": "Problem",
                "slide_count": 2,
                "slide_types": ["content", "chart"],
            },
            {
                "name": "Analysis",
                "slide_count": 4,
                "slide_types": ["content", "chart", "table", "comparison"],
            },
            {
                "name": "Evidence",
                "slide_count": 2,
                "slide_types": ["chart", "comparison"],
            },
            {
                "name": "Recommendations",
                "slide_count": 1,
                "slide_types": ["content"],
            },
            {
                "name": "Conclusion",
                "slide_count": 1,
                "slide_types": ["content"],
            },
        ],
    }
    
    # Simulated data enrichment from Data Enrichment Agent
    data_enrichment = {
        "charts": [
            {
                "type": "bar",
                "title": "Market Growth Trends",
                "data": [15, 23, 31, 42],
                "labels": ["2021", "2022", "2023", "2024"],
            },
            {
                "type": "line",
                "title": "Adoption Rate",
                "data": [12, 28, 45, 67],
                "labels": ["Q1", "Q2", "Q3", "Q4"],
            },
        ],
        "tables": [
            {
                "title": "Financial Metrics",
                "headers": ["Metric", "Current", "Target"],
                "rows": [
                    ["Revenue", "$2.5M", "$5.0M"],
                    ["Growth Rate", "25%", "40%"],
                    ["Market Share", "8%", "15%"],
                ],
            }
        ],
    }
    
    # Generate optimized prompt
    execution_id = str(uuid4())
    
    prompt = prompt_engineering_agent.generate_prompt(
        provider_type=ProviderType.claude,
        topic="Healthcare Digital Transformation Strategy",
        industry="healthcare",
        research_findings=research_findings,
        presentation_plan=presentation_plan,
        data_enrichment=data_enrichment,
        execution_id=execution_id,
    )
    
    print(f"\nPrompt ID: {prompt.prompt_id}")
    print(f"Version: {prompt.version}")
    print(f"Provider: {prompt.provider_type.value}")
    print(f"Estimated Tokens: {prompt.estimated_tokens}")
    print(f"Token Limit: {prompt.token_limit}")
    print(f"\nSystem Prompt (first 200 chars):\n{prompt.system_prompt[:200]}...")
    print(f"\nUser Prompt (first 300 chars):\n{prompt.user_prompt[:300]}...")
    print(f"\nMetadata: {prompt.metadata}")
    
    # Validate token limit
    is_valid, error = prompt_engineering_agent.validate_token_limit(prompt)
    print(f"\nToken Limit Validation: {'✓ PASS' if is_valid else '✗ FAIL'}")
    if error:
        print(f"Error: {error}")
    
    return prompt


async def example_provider_failover():
    """
    Example: Regenerate prompt for provider failover
    """
    print("\n" + "=" * 80)
    print("Example 2: Prompt Regeneration for Provider Failover")
    print("=" * 80)
    
    # Simplified context for failover example
    research_findings = {
        "sections": ["Overview", "Analysis", "Recommendations"],
        "risks": ["Risk 1", "Risk 2"],
        "opportunities": ["Opportunity 1", "Opportunity 2"],
        "terminology": ["term1", "term2", "term3"],
        "context_summary": "Insurance industry risk assessment.",
    }
    
    presentation_plan = {
        "total_slides": 7,
        "sections": [
            {"name": "Title", "slide_count": 1, "slide_types": ["title"]},
            {"name": "Content", "slide_count": 5, "slide_types": ["content"] * 5},
            {"name": "Conclusion", "slide_count": 1, "slide_types": ["content"]},
        ],
    }
    
    # Original prompt for Claude
    print("\n1. Generating original prompt for Claude...")
    original_prompt = prompt_engineering_agent.generate_prompt(
        provider_type=ProviderType.claude,
        topic="Insurance Risk Assessment",
        industry="insurance",
        research_findings=research_findings,
        presentation_plan=presentation_plan,
        execution_id=str(uuid4()),
    )
    
    print(f"   Original Prompt ID: {original_prompt.prompt_id}")
    print(f"   Provider: {original_prompt.provider_type.value}")
    print(f"   Estimated Tokens: {original_prompt.estimated_tokens}")
    
    # Simulate Claude failure - regenerate for OpenAI
    print("\n2. Claude failed - regenerating for OpenAI failover...")
    failover_prompt = prompt_engineering_agent.regenerate_for_failover(
        original_prompt=original_prompt,
        new_provider_type=ProviderType.openai,
        topic="Insurance Risk Assessment",
        industry="insurance",
        research_findings=research_findings,
        presentation_plan=presentation_plan,
        execution_id=str(uuid4()),
    )
    
    print(f"   Failover Prompt ID: {failover_prompt.prompt_id}")
    print(f"   Provider: {failover_prompt.provider_type.value}")
    print(f"   Estimated Tokens: {failover_prompt.estimated_tokens}")
    
    # Compare prompts
    print("\n3. Comparison:")
    print(f"   Prompt IDs differ: {original_prompt.prompt_id != failover_prompt.prompt_id}")
    print(f"   Versions match: {original_prompt.version == failover_prompt.version}")
    print(f"   Token counts: Claude={original_prompt.estimated_tokens}, OpenAI={failover_prompt.estimated_tokens}")


async def example_multi_provider_comparison():
    """
    Example: Compare prompts across all providers
    """
    print("\n" + "=" * 80)
    print("Example 3: Multi-Provider Prompt Comparison")
    print("=" * 80)
    
    # Minimal context for comparison
    research_findings = {
        "sections": ["Intro", "Body", "Conclusion"],
        "risks": ["Risk A"],
        "opportunities": ["Opportunity A"],
        "terminology": ["term"],
        "context_summary": "Technology sector analysis.",
    }
    
    presentation_plan = {
        "total_slides": 5,
        "sections": [
            {"name": "All", "slide_count": 5, "slide_types": ["title", "content", "content", "chart", "content"]},
        ],
    }
    
    providers = [
        ProviderType.claude,
        ProviderType.openai,
        ProviderType.groq,
        ProviderType.local,
    ]
    
    print("\nGenerating prompts for all providers...\n")
    
    for provider in providers:
        prompt = prompt_engineering_agent.generate_prompt(
            provider_type=provider,
            topic="Technology Innovation Trends",
            industry="technology",
            research_findings=research_findings,
            presentation_plan=presentation_plan,
            execution_id=str(uuid4()),
        )
        
        print(f"{provider.value.upper():10} | Tokens: {prompt.estimated_tokens:5} | "
              f"Limit: {prompt.token_limit:7} | ID: {prompt.prompt_id}")


async def example_pipeline_integration():
    """
    Example: Full pipeline integration with prompt versioning
    """
    print("\n" + "=" * 80)
    print("Example 4: Pipeline Integration with Prompt Versioning")
    print("=" * 80)
    
    # Simulate pipeline execution
    execution_id = str(uuid4())
    presentation_id = str(uuid4())
    
    print(f"\nPipeline Execution ID: {execution_id}")
    print(f"Presentation ID: {presentation_id}")
    
    # Step 1: Research Agent completes
    print("\n1. Research Agent completed")
    research_findings = {
        "sections": ["Section 1", "Section 2", "Section 3"],
        "risks": ["Risk 1"],
        "opportunities": ["Opportunity 1"],
        "terminology": ["term1", "term2"],
        "context_summary": "Finance industry analysis.",
    }
    
    # Step 2: Storyboarding Agent completes
    print("2. Storyboarding Agent completed")
    presentation_plan = {
        "total_slides": 8,
        "sections": [
            {"name": "Title", "slide_count": 1, "slide_types": ["title"]},
            {"name": "Content", "slide_count": 6, "slide_types": ["content"] * 6},
            {"name": "End", "slide_count": 1, "slide_types": ["content"]},
        ],
    }
    
    # Step 3: Data Enrichment Agent completes
    print("3. Data Enrichment Agent completed")
    data_enrichment = {"charts": [], "tables": []}
    
    # Step 4: Prompt Engineering Agent generates optimized prompt
    print("4. Prompt Engineering Agent generating optimized prompt...")
    prompt = prompt_engineering_agent.generate_prompt(
        provider_type=ProviderType.claude,
        topic="Financial Market Analysis",
        industry="finance",
        research_findings=research_findings,
        presentation_plan=presentation_plan,
        data_enrichment=data_enrichment,
        execution_id=execution_id,
    )
    
    print(f"   ✓ Prompt generated: {prompt.prompt_id}")
    print(f"   ✓ Version: {prompt.version}")
    print(f"   ✓ Provider: {prompt.provider_type.value}")
    
    # Step 5: Store prompt metadata in pipeline execution
    print("5. Storing prompt metadata in pipeline execution...")
    pipeline_metadata = {
        "prompt_id": prompt.prompt_id,
        "prompt_version": prompt.version,
        "prompt_metadata": prompt.to_dict(),
    }
    
    print(f"   ✓ Prompt ID stored: {pipeline_metadata['prompt_id']}")
    print(f"   ✓ Prompt version stored: {pipeline_metadata['prompt_version']}")
    
    # Step 6: LLM Provider Service would use this prompt
    print("6. LLM Provider Service would invoke provider with optimized prompt")
    print(f"   → Calling {prompt.provider_type.value} with prompt {prompt.prompt_id}")
    
    print("\n✓ Pipeline integration complete")


async def main():
    """Run all examples"""
    await example_prompt_generation()
    await example_provider_failover()
    await example_multi_provider_comparison()
    await example_pipeline_integration()
    
    print("\n" + "=" * 80)
    print("All examples completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
