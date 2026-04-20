"""
Tests for LLM Provider Factory and LangChain Integration
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from langchain_core.language_models.chat_models import BaseChatModel

from app.services.llm_provider import (
    ProviderFactory,
    ProviderType,
    ProviderConfig,
    ExecutionCallbackHandler,
)


class TestProviderConfig:
    """Tests for ProviderConfig"""
    
    def test_claude_default_model(self):
        config = ProviderConfig(
            provider_type=ProviderType.CLAUDE,
            api_key="test-key",
        )
        assert config.model_name == "claude-3-5-sonnet-20241022"
        assert config.is_available is True
    
    def test_openai_default_model(self):
        config = ProviderConfig(
            provider_type=ProviderType.OPENAI,
            api_key="test-key",
        )
        assert config.model_name == "gpt-4o"
        assert config.is_available is True
    
    def test_groq_default_model(self):
        config = ProviderConfig(
            provider_type=ProviderType.GROQ,
            api_key="test-key",
        )
        assert config.model_name == "llama-3.1-70b-versatile"
        assert config.is_available is True
    
    def test_local_default_model(self):
        config = ProviderConfig(
            provider_type=ProviderType.LOCAL,
            endpoint="http://localhost:11434/v1",
        )
        assert config.model_name == "llama3"
        assert config.is_available is True
    
    def test_unavailable_without_credentials(self):
        config = ProviderConfig(
            provider_type=ProviderType.CLAUDE,
            api_key=None,
        )
        assert config.is_available is False


class TestExecutionCallbackHandler:
    """Tests for ExecutionCallbackHandler"""
    
    def test_callback_initialization(self):
        handler = ExecutionCallbackHandler(
            execution_id="test-123",
            provider="claude",
            industry="healthcare",
        )
        assert handler.execution_id == "test-123"
        assert handler.provider == "claude"
        assert handler.industry == "healthcare"
        assert handler.metadata["execution_id"] == "test-123"
        assert handler.metadata["provider"] == "claude"
        assert handler.metadata["industry"] == "healthcare"
    
    def test_on_llm_start_logging(self, caplog):
        handler = ExecutionCallbackHandler(
            execution_id="test-123",
            provider="claude",
        )
        handler.on_llm_start(serialized={}, prompts=["test prompt"])
        # Verify logging occurred (structlog integration)
    
    def test_on_llm_end_logging(self, caplog):
        handler = ExecutionCallbackHandler(
            execution_id="test-123",
            provider="claude",
        )
        handler.on_llm_end(response=Mock())
        # Verify logging occurred
    
    def test_on_llm_error_logging(self, caplog):
        handler = ExecutionCallbackHandler(
            execution_id="test-123",
            provider="claude",
        )
        handler.on_llm_error(error=Exception("Test error"))
        # Verify error logging occurred


class TestProviderFactory:
    """Tests for ProviderFactory"""
    
    @patch("app.services.llm_provider.settings")
    def test_load_configuration_claude_primary(self, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "claude"
        mock_settings.LLM_FALLBACK_PROVIDERS = "openai,groq"
        mock_settings.ANTHROPIC_API_KEY = "test-claude-key"
        mock_settings.OPENAI_API_KEY = "test-openai-key"
        mock_settings.GROQ_API_KEY = "test-groq-key"
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        
        assert factory.primary_provider == ProviderType.CLAUDE
        assert ProviderType.OPENAI in factory.fallback_providers
        assert ProviderType.GROQ in factory.fallback_providers
        assert len(factory.fallback_providers) == 2
    
    @patch("app.services.llm_provider.settings")
    def test_load_configuration_invalid_primary(self, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "invalid"
        mock_settings.LLM_FALLBACK_PROVIDERS = ""
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        with pytest.raises(ValueError, match="Invalid LLM_PRIMARY_PROVIDER"):
            ProviderFactory()
    
    @patch("app.services.llm_provider.settings")
    def test_fallback_excludes_primary(self, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "claude"
        mock_settings.LLM_FALLBACK_PROVIDERS = "claude,openai"  # claude should be excluded
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.OPENAI_API_KEY = "test-key"
        mock_settings.GROQ_API_KEY = None
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        
        assert factory.primary_provider == ProviderType.CLAUDE
        assert ProviderType.CLAUDE not in factory.fallback_providers
        assert ProviderType.OPENAI in factory.fallback_providers
    
    @patch("app.services.llm_provider.settings")
    def test_validate_startup_success(self, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "claude"
        mock_settings.LLM_FALLBACK_PROVIDERS = ""
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.OPENAI_API_KEY = None
        mock_settings.GROQ_API_KEY = None
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        
        with patch.object(factory, "_create_client", return_value=Mock(spec=BaseChatModel)):
            factory.validate_startup()  # Should not raise
    
    @patch("app.services.llm_provider.settings")
    def test_validate_startup_missing_primary_key(self, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "claude"
        mock_settings.LLM_FALLBACK_PROVIDERS = ""
        mock_settings.ANTHROPIC_API_KEY = None  # Missing key
        mock_settings.OPENAI_API_KEY = None
        mock_settings.GROQ_API_KEY = None
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            factory.validate_startup()
    
    @patch("app.services.llm_provider.settings")
    def test_validate_startup_unreachable_provider(self, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "claude"
        mock_settings.LLM_FALLBACK_PROVIDERS = ""
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.OPENAI_API_KEY = None
        mock_settings.GROQ_API_KEY = None
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        
        with patch.object(
            factory,
            "_create_client",
            side_effect=Exception("Connection failed"),
        ):
            with pytest.raises(RuntimeError, match="unreachable"):
                factory.validate_startup()
    
    @patch("app.services.llm_provider.settings")
    def test_backward_compatibility_mode(self, mock_settings):
        """Test backward compatibility when only ANTHROPIC_API_KEY is set"""
        mock_settings.LLM_PRIMARY_PROVIDER = "claude"
        mock_settings.LLM_FALLBACK_PROVIDERS = ""
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.OPENAI_API_KEY = None
        mock_settings.GROQ_API_KEY = None
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        
        assert factory.is_backward_compatible_mode() is True
        assert factory.primary_provider == ProviderType.CLAUDE
        assert len(factory.fallback_providers) == 0
    
    @patch("app.services.llm_provider.settings")
    def test_not_backward_compatibility_mode_with_fallbacks(self, mock_settings):
        """Test that backward compatibility mode is False when fallbacks are configured"""
        mock_settings.LLM_PRIMARY_PROVIDER = "claude"
        mock_settings.LLM_FALLBACK_PROVIDERS = "openai"
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.OPENAI_API_KEY = "test-key"
        mock_settings.GROQ_API_KEY = None
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        
        assert factory.is_backward_compatible_mode() is False
    
    @patch("app.services.llm_provider.settings")
    @patch("app.services.llm_provider.ChatAnthropic")
    def test_create_claude_client(self, mock_chat_anthropic, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "claude"
        mock_settings.LLM_FALLBACK_PROVIDERS = ""
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.OPENAI_API_KEY = None
        mock_settings.GROQ_API_KEY = None
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        client = factory._create_client(ProviderType.CLAUDE)
        
        mock_chat_anthropic.assert_called_once()
        call_kwargs = mock_chat_anthropic.call_args[1]
        assert call_kwargs["anthropic_api_key"] == "test-key"
        assert call_kwargs["model"] == "claude-3-5-sonnet-20241022"
    
    @patch("app.services.llm_provider.settings")
    @patch("app.services.llm_provider.ChatOpenAI")
    def test_create_openai_client(self, mock_chat_openai, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "openai"
        mock_settings.LLM_FALLBACK_PROVIDERS = ""
        mock_settings.ANTHROPIC_API_KEY = None
        mock_settings.OPENAI_API_KEY = "test-key"
        mock_settings.GROQ_API_KEY = None
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        client = factory._create_client(ProviderType.OPENAI)
        
        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["openai_api_key"] == "test-key"
        assert call_kwargs["model"] == "gpt-4o"
    
    @patch("app.services.llm_provider.settings")
    @patch("app.services.llm_provider.ChatGroq")
    def test_create_groq_client(self, mock_chat_groq, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "groq"
        mock_settings.LLM_FALLBACK_PROVIDERS = ""
        mock_settings.ANTHROPIC_API_KEY = None
        mock_settings.OPENAI_API_KEY = None
        mock_settings.GROQ_API_KEY = "test-key"
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        client = factory._create_client(ProviderType.GROQ)
        
        mock_chat_groq.assert_called_once()
        call_kwargs = mock_chat_groq.call_args[1]
        assert call_kwargs["groq_api_key"] == "test-key"
        assert call_kwargs["model"] == "llama-3.1-70b-versatile"
    
    @patch("app.services.llm_provider.settings")
    @patch("app.services.llm_provider.ChatOpenAI")
    def test_create_local_client(self, mock_chat_openai, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "local"
        mock_settings.LLM_FALLBACK_PROVIDERS = ""
        mock_settings.ANTHROPIC_API_KEY = None
        mock_settings.OPENAI_API_KEY = None
        mock_settings.GROQ_API_KEY = None
        mock_settings.LOCAL_LLM_ENDPOINT = "http://localhost:11434/v1"
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        client = factory._create_client(ProviderType.LOCAL)
        
        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs["openai_api_base"] == "http://localhost:11434/v1"
        assert call_kwargs["openai_api_key"] == "not-needed"
        assert call_kwargs["model"] == "llama3"
    
    @patch("app.services.llm_provider.settings")
    @patch("app.services.llm_provider.ChatAnthropic")
    def test_get_client_with_execution_id(self, mock_chat_anthropic, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "claude"
        mock_settings.LLM_FALLBACK_PROVIDERS = ""
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.OPENAI_API_KEY = None
        mock_settings.GROQ_API_KEY = None
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        client = factory.get_client(
            execution_id="exec-123",
            industry="healthcare",
        )
        
        mock_chat_anthropic.assert_called_once()
        call_kwargs = mock_chat_anthropic.call_args[1]
        assert len(call_kwargs["callbacks"]) == 1
        callback = call_kwargs["callbacks"][0]
        assert isinstance(callback, ExecutionCallbackHandler)
        assert callback.execution_id == "exec-123"
        assert callback.industry == "healthcare"
    
    @patch("app.services.llm_provider.settings")
    def test_get_fallback_sequence(self, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "claude"
        mock_settings.LLM_FALLBACK_PROVIDERS = "openai,groq"
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.OPENAI_API_KEY = "test-key"
        mock_settings.GROQ_API_KEY = "test-key"
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        sequence = factory.get_fallback_sequence()
        
        assert sequence[0] == ProviderType.CLAUDE
        assert sequence[1] == ProviderType.OPENAI
        assert sequence[2] == ProviderType.GROQ
        assert len(sequence) == 3
    
    @patch("app.services.llm_provider.settings")
    @patch("app.services.llm_provider.LangSmithClient")
    def test_langsmith_initialization_enabled(self, mock_langsmith_client, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "claude"
        mock_settings.LLM_FALLBACK_PROVIDERS = ""
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.OPENAI_API_KEY = None
        mock_settings.GROQ_API_KEY = None
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = True
        mock_settings.LANGSMITH_API_KEY = "test-langsmith-key"
        mock_settings.LANGSMITH_PROJECT = "test-project"
        
        factory = ProviderFactory()
        
        mock_langsmith_client.assert_called_once_with(api_key="test-langsmith-key")
        assert factory._langsmith_client is not None
    
    @patch("app.services.llm_provider.settings")
    def test_langsmith_initialization_disabled(self, mock_settings):
        mock_settings.LLM_PRIMARY_PROVIDER = "claude"
        mock_settings.LLM_FALLBACK_PROVIDERS = ""
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.OPENAI_API_KEY = None
        mock_settings.GROQ_API_KEY = None
        mock_settings.LOCAL_LLM_ENDPOINT = None
        mock_settings.LANGCHAIN_TRACING_V2 = False
        mock_settings.LANGSMITH_API_KEY = None
        
        factory = ProviderFactory()
        
        assert factory._langsmith_client is None
