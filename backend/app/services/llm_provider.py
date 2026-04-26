"""
LLM Provider Factory and LangChain Integration

This module implements the Provider Factory pattern for managing multiple LLM providers
with automatic failover, health monitoring, and LangSmith tracing integration.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
import structlog

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.callbacks import BaseCallbackHandler
from langsmith import Client as LangSmithClient

from app.core.config import settings
from app.services.provider_health import health_monitor, ExponentialBackoffRetry


logger = structlog.get_logger(__name__)


class ProviderType(str, Enum):
    """Supported LLM provider types"""
    CLAUDE = "claude"
    OPENAI = "openai"
    GROQ = "groq"
    LOCAL = "local"


class ProviderConfig:
    """Configuration for a specific LLM provider"""
    
    def __init__(
        self,
        provider_type: ProviderType,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.provider_type = provider_type
        self.api_key = api_key
        self.endpoint = endpoint
        self.model_name = model_name or self._default_model()
        self.temperature = temperature
        self.max_tokens = max_tokens if max_tokens != 4096 else self._default_max_tokens()
        self.is_available = self._check_availability()
    
    def _default_model(self) -> str:
        """Get default model name for provider"""
        defaults = {
            ProviderType.CLAUDE: "claude-haiku-4-5-20251001",
            ProviderType.OPENAI: "gpt-4o",
            ProviderType.GROQ: "llama-3.3-70b-versatile",
            ProviderType.LOCAL: "llama3",
        }
        return defaults.get(self.provider_type, "")
    
    def _default_max_tokens(self) -> int:
        """Get default max_tokens per provider — large enough for full presentations"""
        defaults = {
            ProviderType.CLAUDE: 32000,   # Claude supports up to 64k output - increased for full 13-slide presentations
            ProviderType.OPENAI: 16000,
            ProviderType.GROQ: 16000,     # Groq supports up to 32k — use 16k for safety
            ProviderType.LOCAL: 4096,
        }
        return defaults.get(self.provider_type, 4096)
    
    def _check_availability(self) -> bool:
        """Check if provider credentials are available"""
        if self.provider_type == ProviderType.LOCAL:
            return bool(self.endpoint)
        return bool(self.api_key)


class ExecutionCallbackHandler(BaseCallbackHandler):
    """Custom callback handler for LangSmith tracing with execution metadata"""
    
    def __init__(self, execution_id: str, provider: str, industry: Optional[str] = None):
        super().__init__()
        self.execution_id = execution_id
        self.provider = provider
        self.industry = industry
        self.metadata = {
            "execution_id": execution_id,
            "provider": provider,
            "industry": industry,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        """Log LLM call start"""
        logger.info(
            "llm_call_started",
            execution_id=self.execution_id,
            provider=self.provider,
            prompt_count=len(prompts),
        )
    
    def on_llm_end(self, response: Any, **kwargs) -> None:
        """Log LLM call completion"""
        logger.info(
            "llm_call_completed",
            execution_id=self.execution_id,
            provider=self.provider,
        )
    
    def on_llm_error(self, error: Exception, **kwargs) -> None:
        """Log LLM call error"""
        logger.error(
            "llm_call_failed",
            execution_id=self.execution_id,
            provider=self.provider,
            error=str(error),
        )


class ProviderFactory:
    """
    Factory for creating and managing LLM provider instances with automatic failover.
    
    Reads configuration from environment variables at startup and provides
    unified interface for all supported providers.
    """
    
    def __init__(self):
        self.primary_provider: Optional[ProviderType] = None
        self.fallback_providers: List[ProviderType] = []
        self.provider_configs: Dict[ProviderType, ProviderConfig] = {}
        self._langsmith_client: Optional[LangSmithClient] = None
        
        # Initialize on creation
        self._load_configuration()
        self._initialize_langsmith()
        self._initialize_health_monitor()
    
    def _load_configuration(self) -> None:
        """Load provider configuration from environment variables"""
        logger.info("loading_provider_configuration")
        
        # Parse primary provider
        try:
            self.primary_provider = ProviderType(settings.LLM_PRIMARY_PROVIDER.lower())
        except ValueError:
            logger.error(
                "invalid_primary_provider",
                provider=settings.LLM_PRIMARY_PROVIDER,
            )
            raise ValueError(
                f"Invalid LLM_PRIMARY_PROVIDER: {settings.LLM_PRIMARY_PROVIDER}. "
                f"Must be one of: {[p.value for p in ProviderType]}"
            )
        
        # Parse fallback providers
        if settings.LLM_FALLBACK_PROVIDERS:
            fallback_list = [p.strip() for p in settings.LLM_FALLBACK_PROVIDERS.split(",")]
            for provider_str in fallback_list:
                try:
                    provider = ProviderType(provider_str.lower())
                    if provider != self.primary_provider:
                        self.fallback_providers.append(provider)
                except ValueError:
                    logger.warning(
                        "invalid_fallback_provider",
                        provider=provider_str,
                    )
        
        # Create provider configurations
        self.provider_configs = {
            ProviderType.CLAUDE: ProviderConfig(
                provider_type=ProviderType.CLAUDE,
                api_key=settings.ANTHROPIC_API_KEY,
            ),
            ProviderType.OPENAI: ProviderConfig(
                provider_type=ProviderType.OPENAI,
                api_key=settings.OPENAI_API_KEY,
            ),
            ProviderType.GROQ: ProviderConfig(
                provider_type=ProviderType.GROQ,
                api_key=settings.GROQ_API_KEY,
            ),
            ProviderType.LOCAL: ProviderConfig(
                provider_type=ProviderType.LOCAL,
                endpoint=settings.LOCAL_LLM_ENDPOINT,
            ),
        }
        
        logger.info(
            "provider_configuration_loaded",
            primary=self.primary_provider.value,
            fallbacks=[p.value for p in self.fallback_providers],
        )
    
    def _initialize_langsmith(self) -> None:
        """Initialize LangSmith client if tracing is enabled"""
        if settings.LANGCHAIN_TRACING_V2 and settings.LANGSMITH_API_KEY:
            try:
                self._langsmith_client = LangSmithClient(
                    api_key=settings.LANGSMITH_API_KEY,
                )
                logger.info("langsmith_tracing_enabled", project=settings.LANGSMITH_PROJECT)
            except Exception as e:
                logger.warning("langsmith_initialization_failed", error=str(e))
                self._langsmith_client = None
        else:
            logger.info("langsmith_tracing_disabled")
    
    def _initialize_health_monitor(self) -> None:
        """Initialize health monitor with primary provider"""
        if self.primary_provider:
            health_monitor.set_primary_provider(self.primary_provider)
            logger.info("health_monitor_initialized", primary=self.primary_provider.value)
    
    def validate_startup(self) -> None:
        """
        Validate provider configuration at startup.
        Fails fast if primary provider is not available.
        """
        logger.info("validating_provider_configuration")
        
        # Check primary provider availability
        primary_config = self.provider_configs.get(self.primary_provider)
        if not primary_config or not primary_config.is_available:
            error_msg = self._get_missing_credential_error(self.primary_provider)
            logger.error(
                "primary_provider_unavailable",
                provider=self.primary_provider.value,
                error=error_msg,
            )
            raise RuntimeError(error_msg)
        
        # Test primary provider connectivity
        try:
            client = self._create_client(self.primary_provider)
            logger.info(
                "primary_provider_validated",
                provider=self.primary_provider.value,
                model=primary_config.model_name,
            )
        except Exception as e:
            logger.error(
                "primary_provider_unreachable",
                provider=self.primary_provider.value,
                error=str(e),
            )
            raise RuntimeError(
                f"Primary provider {self.primary_provider.value} is unreachable: {str(e)}"
            )
        
        # Log fallback provider status
        available_fallbacks = []
        for provider in self.fallback_providers:
            config = self.provider_configs.get(provider)
            if config and config.is_available:
                available_fallbacks.append(provider.value)
        
        if available_fallbacks:
            logger.info(
                "fallback_providers_available",
                providers=available_fallbacks,
            )
        else:
            logger.warning("no_fallback_providers_available")
    
    def _get_missing_credential_error(self, provider: ProviderType) -> str:
        """Get helpful error message for missing credentials"""
        credential_map = {
            ProviderType.CLAUDE: "ANTHROPIC_API_KEY",
            ProviderType.OPENAI: "OPENAI_API_KEY",
            ProviderType.GROQ: "GROQ_API_KEY",
            ProviderType.LOCAL: "LOCAL_LLM_ENDPOINT",
        }
        credential = credential_map.get(provider, "API_KEY")
        return (
            f"Primary provider '{provider.value}' is not configured. "
            f"Please set {credential} in your environment variables."
        )
    
    def _create_client(
        self,
        provider: ProviderType,
        execution_id: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> BaseChatModel:
        """Create LangChain client for specified provider"""
        config = self.provider_configs.get(provider)
        if not config or not config.is_available:
            raise ValueError(f"Provider {provider.value} is not available")
        
        # Prepare callbacks for LangSmith tracing
        callbacks = []
        if execution_id:
            callbacks.append(
                ExecutionCallbackHandler(
                    execution_id=execution_id,
                    provider=provider.value,
                    industry=industry,
                )
            )
        
        # Create provider-specific client
        if provider == ProviderType.CLAUDE:
            return ChatAnthropic(
                anthropic_api_key=config.api_key,
                model=config.model_name,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                callbacks=callbacks,
                default_request_timeout=120.0,  # 2 minute timeout for HTTP requests
            )
        
        elif provider == ProviderType.OPENAI:
            return ChatOpenAI(
                openai_api_key=config.api_key,
                model=config.model_name,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                callbacks=callbacks,
                request_timeout=120.0,  # 2 minute timeout for HTTP requests
            )
        
        elif provider == ProviderType.GROQ:
            return ChatGroq(
                groq_api_key=config.api_key,
                model=config.model_name,
                temperature=1.0,  # Match Groq example
                max_tokens=16000,  # Large enough for full presentation JSON
                callbacks=callbacks,
                timeout=120.0,  # 2 minute timeout for HTTP requests
            )
        
        elif provider == ProviderType.LOCAL:
            return ChatOpenAI(
                openai_api_base=config.endpoint,
                openai_api_key="not-needed",  # Local LLMs don't need API key
                model=config.model_name,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                callbacks=callbacks,
            )
        
        else:
            raise ValueError(f"Unsupported provider: {provider.value}")
    
    def get_client(
        self,
        execution_id: Optional[str] = None,
        industry: Optional[str] = None,
        preferred_provider: Optional[ProviderType] = None,
    ) -> BaseChatModel:
        """
        Get LangChain client for the specified or primary provider.
        
        Args:
            execution_id: Unique execution ID for tracing
            industry: Industry context for tracing metadata
            preferred_provider: Override primary provider (used for failover)
        
        Returns:
            Configured LangChain chat model client
        """
        provider = preferred_provider or self.primary_provider
        
        logger.info(
            "creating_llm_client",
            provider=provider.value,
            execution_id=execution_id,
            industry=industry,
        )
        
        return self._create_client(provider, execution_id, industry)
    
    def get_fallback_sequence(self) -> List[ProviderType]:
        """Get ordered list of providers for failover (primary + fallbacks)"""
        return [self.primary_provider] + self.fallback_providers
    
    def is_backward_compatible_mode(self) -> bool:
        """
        Check if running in backward compatibility mode.
        Returns True if only ANTHROPIC_API_KEY is set with no explicit provider config.
        """
        return (
            self.primary_provider == ProviderType.CLAUDE
            and not self.fallback_providers
            and settings.ANTHROPIC_API_KEY
            and not settings.OPENAI_API_KEY
            and not settings.GROQ_API_KEY
        )
    
    async def call_with_failover(
        self,
        func,
        execution_id: Optional[str] = None,
        industry: Optional[str] = None,
        *args,
        **kwargs,
    ):
        """
        Call LLM function with automatic failover support.
        
        Implements:
        - Automatic provider selection based on health
        - Exponential backoff retry with jitter
        - Health metric recording
        - Failover to secondary providers on failure
        
        Args:
            func: Function to call with LLM client
            execution_id: Execution ID for tracing
            industry: Industry context for tracing
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        
        Returns:
            Result from func
        
        Raises:
            Exception if all providers fail
        """
        import time
        
        # Get available providers
        available_providers = self.get_fallback_sequence()
        
        # Select best provider based on health
        selected_provider = health_monitor.select_provider(available_providers)
        if not selected_provider:
            raise RuntimeError("No available LLM providers")
        
        # Try each provider in sequence
        retry_handler = ExponentialBackoffRetry(
            base_delay_seconds=2.0,
            max_delay_seconds=32.0,
            max_retries=3,
        )
        
        last_error = None
        for provider in available_providers:
            # Skip if circuit is open and can't recover
            metrics = health_monitor.metrics[provider]
            if metrics.circuit_open and not metrics.can_attempt_recovery():
                logger.info(
                    "skipping_provider_circuit_open",
                    provider=provider.value,
                )
                continue
            
            logger.info(
                "attempting_provider",
                provider=provider.value,
                execution_id=execution_id,
            )
            
            # Check per-provider rate limit before attempting call
            try:
                from app.services.rate_limiter import check_provider_rate_limit
                rl_result = await check_provider_rate_limit(provider.value)
                if not rl_result.allowed:
                    logger.warning(
                        "provider_rate_limit_skip",
                        provider=provider.value,
                        retry_after=rl_result.retry_after,
                    )
                    continue
            except Exception:
                pass  # Fail open if rate limiter is unavailable

            # Get client for this provider
            try:
                client = self.get_client(
                    execution_id=execution_id,
                    industry=industry,
                    preferred_provider=provider,
                )
            except Exception as e:
                logger.error(
                    "client_creation_failed",
                    provider=provider.value,
                    error=str(e),
                )
                continue
            
            # Try calling with retry
            start_time = time.time()
            
            try:
                result = await func(client, *args, **kwargs)
                
                # Record success
                response_time_ms = (time.time() - start_time) * 1000
                health_monitor.record_call(provider, success=True, response_time_ms=response_time_ms)
                
                # Update cache
                await health_monitor.update_health_cache()
                
                logger.info(
                    "provider_call_succeeded",
                    provider=provider.value,
                    response_time_ms=response_time_ms,
                    execution_id=execution_id,
                )
                
                return result
                
            except Exception as e:
                # Record failure
                response_time_ms = (time.time() - start_time) * 1000
                health_monitor.record_call(provider, success=False, response_time_ms=response_time_ms)
                
                # Update cache
                await health_monitor.update_health_cache()
                
                logger.error(
                    "provider_call_failed",
                    provider=provider.value,
                    error=str(e),
                    response_time_ms=response_time_ms,
                    execution_id=execution_id,
                )
                
                last_error = e
                
                # If this was the primary provider, check if we should failover
                if provider == self.primary_provider and health_monitor.should_failover():
                    # 30.3 — Trace provider failover event
                    next_providers = [p for p in available_providers if p != provider]
                    to_provider = next_providers[0].value if next_providers else "none"
                    try:
                        from app.services.observability import observability as obs
                        obs.trace_provider_failover(
                            execution_id=execution_id or "unknown",
                            from_provider=provider.value,
                            to_provider=to_provider,
                            failure_reason=str(e),
                        )
                    except Exception:
                        pass
                    logger.warning(
                        "primary_provider_failed_attempting_failover",
                        provider=provider.value,
                    )
                    continue
                
                # Try next provider
                continue
        
        # All providers failed
        logger.error(
            "all_providers_failed",
            execution_id=execution_id,
            error=str(last_error),
        )
        raise RuntimeError(f"All LLM providers failed. Last error: {str(last_error)}")


# Global provider factory instance
provider_factory = ProviderFactory()
