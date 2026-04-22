"""
Shared LLM utilities for agent enhancements.
Provides consistent error handling, retries, and observability.
"""

import asyncio
from typing import Any, Dict, Optional
import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel

from app.services.llm_provider import provider_factory

logger = structlog.get_logger(__name__)


class LLMEnhancementHelper:
    """Base class for LLM-enhanced agent operations."""
    
    TIMEOUT_SECONDS = 20
    MAX_RETRIES = 2
    
    async def call_llm_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        pydantic_model: type[BaseModel],
        execution_id: str,
        industry: str = "general",
    ) -> Dict[str, Any]:
        """
        Call LLM with automatic retry and error handling.
        
        Args:
            system_prompt: System prompt for LLM
            user_prompt: User prompt for LLM
            pydantic_model: Pydantic model for output parsing
            execution_id: Execution ID for tracing
            industry: Industry context for provider selection
            
        Returns:
            Parsed JSON response as dict
            
        Raises:
            RuntimeError: If all retries fail
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                async def call_llm(client):
                    parser = JsonOutputParser(pydantic_object=pydantic_model)
                    messages = [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=user_prompt),
                    ]
                    response = await client.ainvoke(messages)
                    return parser.parse(response.content)
                
                result = await asyncio.wait_for(
                    provider_factory.call_with_failover(
                        call_llm,
                        execution_id=execution_id,
                        industry=industry,
                    ),
                    timeout=self.TIMEOUT_SECONDS,
                )
                
                logger.info(
                    "llm_enhancement_success",
                    attempt=attempt + 1,
                    execution_id=execution_id,
                )
                return result
                
            except asyncio.TimeoutError:
                logger.warning(
                    "llm_enhancement_timeout",
                    attempt=attempt + 1,
                    timeout=self.TIMEOUT_SECONDS,
                    execution_id=execution_id,
                )
                if attempt == self.MAX_RETRIES - 1:
                    raise RuntimeError(f"LLM enhancement timed out after {self.MAX_RETRIES} attempts")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as e:
                logger.warning(
                    "llm_enhancement_attempt_failed",
                    attempt=attempt + 1,
                    error=str(e),
                    execution_id=execution_id,
                )
                if attempt == self.MAX_RETRIES - 1:
                    raise RuntimeError(f"LLM enhancement failed: {str(e)}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        raise RuntimeError("LLM enhancement failed after all retries")
