"""
Example LLM Service with Health Monitoring and Failover

Demonstrates how to use the provider factory with automatic failover.
"""

import asyncio
from typing import Optional

import structlog
from langchain_core.messages import HumanMessage

from app.services.llm_provider import provider_factory
from app.services.provider_health import health_monitor


logger = structlog.get_logger(__name__)


async def generate_presentation_content(
    topic: str,
    execution_id: str,
    industry: Optional[str] = None,
) -> dict:
    """
    Generate presentation content with automatic provider failover.
    
    This function demonstrates the complete failover workflow:
    1. Health monitor selects best available provider
    2. Attempts call with exponential backoff retry
    3. Records success/failure metrics
    4. Automatically fails over to secondary providers if needed
    5. Restores primary provider when health recovers
    
    Args:
        topic: Presentation topic
        execution_id: Unique execution ID for tracing
        industry: Industry context (optional)
    
    Returns:
        Generated content dictionary
    
    Raises:
        RuntimeError: If all providers fail
    """
    logger.info(
        "generating_presentation_content",
        topic=topic,
        execution_id=execution_id,
        industry=industry,
    )
    
    # Define the LLM call function
    async def call_llm(client, prompt: str):
        """Call LLM with the given prompt"""
        messages = [HumanMessage(content=prompt)]
        response = await client.ainvoke(messages)
        return response.content
    
    # Prepare prompt
    prompt = f"""Generate a presentation outline for the following topic:

Topic: {topic}
Industry: {industry or "General"}

Please provide a structured outline with:
1. Title
2. Key sections (3-5)
3. Main points for each section

Format the response as JSON."""
    
    try:
        # Call with automatic failover
        result = await provider_factory.call_with_failover(
            call_llm,
            execution_id=execution_id,
            industry=industry,
            prompt=prompt,
        )
        
        logger.info(
            "presentation_content_generated",
            execution_id=execution_id,
            result_length=len(result) if result else 0,
        )
        
        return {
            "content": result,
            "provider": health_monitor.current_provider.value if health_monitor.current_provider else None,
            "failover_active": health_monitor.failover_active,
        }
        
    except Exception as e:
        logger.error(
            "presentation_content_generation_failed",
            execution_id=execution_id,
            error=str(e),
        )
        raise


async def get_provider_health_summary() -> dict:
    """
    Get health summary for all providers.
    
    Returns:
        Dictionary with health status for each provider
    """
    summary = {
        "primary_provider": health_monitor.primary_provider.value if health_monitor.primary_provider else None,
        "current_provider": health_monitor.current_provider.value if health_monitor.current_provider else None,
        "failover_active": health_monitor.failover_active,
        "providers": {},
    }
    
    for provider_type in health_monitor.metrics.keys():
        status = health_monitor.get_health_status(provider_type)
        summary["providers"][provider_type.value] = status
    
    return summary


async def example_usage():
    """
    Example usage demonstrating health monitoring and failover.
    """
    # Initialize provider factory (normally done at startup)
    provider_factory.validate_startup()
    
    # Generate content with automatic failover
    try:
        result = await generate_presentation_content(
            topic="AI in Healthcare",
            execution_id="example-001",
            industry="healthcare",
        )
        
        print(f"Generated content using provider: {result['provider']}")
        print(f"Failover active: {result['failover_active']}")
        print(f"Content preview: {result['content'][:200]}...")
        
    except Exception as e:
        print(f"Generation failed: {e}")
    
    # Get health summary
    health_summary = await get_provider_health_summary()
    print("\nProvider Health Summary:")
    print(f"Primary: {health_summary['primary_provider']}")
    print(f"Current: {health_summary['current_provider']}")
    print(f"Failover: {health_summary['failover_active']}")
    
    for provider, status in health_summary["providers"].items():
        print(f"\n{provider}:")
        print(f"  Success Rate: {status['success_rate']:.2%}")
        print(f"  Avg Response Time: {status['avg_response_time_ms']:.2f}ms")
        print(f"  Healthy: {status['is_healthy']}")
        print(f"  Circuit Open: {status['circuit_open']}")


if __name__ == "__main__":
    asyncio.run(example_usage())
