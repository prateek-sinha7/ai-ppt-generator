from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # CORS — explicit whitelist; add production domains here or via env var
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    # Allowed CORS methods and headers (used by SecurityHeadersMiddleware)
    CORS_ALLOW_CREDENTIALS: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/presentations"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # MinIO / S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "presentations"
    MINIO_USE_SSL: bool = False

    # LLM Providers
    LLM_PRIMARY_PROVIDER: str = "claude"
    LLM_FALLBACK_PROVIDERS: str = ""
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    LOCAL_LLM_ENDPOINT: Optional[str] = None

    # LangSmith
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "ai-presentation-platform"
    LANGCHAIN_TRACING_V2: bool = False

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Cost control
    MAX_LLM_CALLS_PER_REQUEST: int = 4
    COST_CEILING_USD: float = 1.0
    TENANT_DAILY_COST_THRESHOLD_USD: float = 10.0
    COST_ALERT_WEBHOOK_URL: Optional[str] = None

    # PPTX Service (Node.js pptxgenjs microservice)
    PPTX_SERVICE_URL: str = "http://pptx-service:3001"

    # Phase 5 Optimizations (Cost Reduction)
    ENABLE_PHASE5_OPTIMIZATIONS: bool = True
    ENABLE_LLM_CACHING: bool = True
    ENABLE_BATCH_PROCESSING: bool = True
    ENABLE_SELECTIVE_ENHANCEMENT: bool = True


settings = Settings()
