"""
Example usage of the LLM Provider Factory

This module demonstrates how to use the provider factory to interact with
different LLM providers through a unified interface.
"""

from typing import Optional
import structlog

from langchain_core.messages import HumanMessage, SystemMessage
from app.services.llm_provider import provider_factory, ProviderType

logger = structlog.get_logger(__name__)


async def generate_presentation_content(
    topic: str,
    execution_id: str,
    industry: Optional[str] = None,
) -> str:
    """
    Example function showing how to use the provider factory to generate content.
    
    Args:
        topic: Presentation topic
        execution_id: Unique execution ID for tracing
        industry: Detected industry for context
    
    Returns:
        Generated content from LLM
    """
    logger.info(
        "generating_presentation_content",
        topic=topic,
        execution_id=execution_id,
        industry=industry,
    )
    
    # Get the primary provider client with tracing
    client = provider_factory.get_client(
        execution_id=execution_id,
        industry=industry,
    )
    
    # Prepare messages
    system_message = SystemMessage(
        content="You are an expert presentation creator. Generate structured content."
    )
    human_message = HumanMessage(
        content=f"Create a presentation outline for: {topic}"
    )
    
    try:
        # Invoke the LLM (this will be traced in LangSmith if enabled)
        response = await client.ainvoke([system_message, human_message])
        
        logger.info(
            "content_generation_successful",
            execution_id=execution_id,
            provider=provider_factory.primary_provider.value,
        )
        
        return response.content
    
    except Exception as e:
        logger.error(
            "content_generation_failed",
            execution_id=execution_id,
            error=str(e),
        )
        raise


async def generate_with_fallback(
    topic: str,
    execution_id: str,
    industry: Optional[str] = None,
) -> str:
    """
    Example function showing how to implement manual fallback logic.
    
    Args:
        topic: Presentation topic
        execution_id: Unique execution ID for tracing
        industry: Detected industry for context
    
    Returns:
        Generated content from LLM (using fallback if primary fails)
    """
    # Get the fallback sequence (primary + fallbacks)
    providers = provider_factory.get_fallback_sequence()
    
    last_error = None
    
    for provider in providers:
        try:
            logger.info(
                "attempting_provider",
                provider=provider.value,
                execution_id=execution_id,
            )
            
            # Get client for specific provider
            client = provider_factory.get_client(
                execution_id=execution_id,
                industry=industry,
                preferred_provider=provider,
            )
            
            # Prepare messages
            system_message = SystemMessage(
                content="You are an expert presentation creator."
            )
            human_message = HumanMessage(
                content=f"Create a presentation outline for: {topic}"
            )
            
            # Invoke the LLM
            response = await client.ainvoke([system_message, human_message])
            
            logger.info(
                "provider_success",
                provider=provider.value,
                execution_id=execution_id,
            )
            
            return response.content
        
        except Exception as e:
            logger.warning(
                "provider_failed",
                provider=provider.value,
                execution_id=execution_id,
                error=str(e),
            )
            last_error = e
            continue
    
    # All providers failed
    logger.error(
        "all_providers_failed",
        execution_id=execution_id,
        providers=[p.value for p in providers],
    )
    raise RuntimeError(
        f"All providers failed. Last error: {str(last_error)}"
    )


def check_provider_status() -> dict:
    """
    Check the status of configured providers.
    
    Returns:
        Dictionary with provider status information
    """
    return {
        "primary_provider": provider_factory.primary_provider.value,
        "fallback_providers": [p.value for p in provider_factory.fallback_providers],
        "backward_compatible_mode": provider_factory.is_backward_compatible_mode(),
        "langsmith_enabled": provider_factory._langsmith_client is not None,
    }
