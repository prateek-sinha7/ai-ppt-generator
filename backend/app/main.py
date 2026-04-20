from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.api.v1.auth import router as auth_router
from app.api.v1.presentations import router as presentations_router
from app.api.v1.slide_editing import router as slide_editing_router
from app.api.v1.export_templates_admin import router as export_templates_admin_router
from app.api.v1.export_templates_admin import internal_router as internal_admin_router
from app.api.v1.health import router as health_router
from app.api.v1.schema_versioning import router as schema_versioning_router
from app.core.config import settings
from app.middleware.api_versioning import APIVersioningMiddleware, get_api_versions_response
from app.middleware.audit import AuditMiddleware
from app.middleware.rbac import RBACMiddleware
from app.middleware.sanitization import SanitizationMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.tenant import TenantMiddleware
from app.services.llm_provider import provider_factory
from app.services.health_monitor_task import health_monitor_task
from app.services.redis_cache import redis_cache
from app.services.cache_warming_task import cache_warming_task

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events"""
    # Startup: Validate LLM provider configuration
    logger.info("application_startup_initiated")
    try:
        provider_factory.validate_startup()
        logger.info("llm_provider_validation_successful")
    except Exception as e:
        logger.error("llm_provider_validation_failed", error=str(e))
        raise
    
    # Startup: Connect to Redis
    try:
        await redis_cache.connect()
        logger.info("redis_connection_successful")
    except Exception as e:
        logger.error("redis_connection_failed", error=str(e))
        raise
    
    # Startup: Start health monitor background task
    try:
        await health_monitor_task.start()
        logger.info("health_monitor_task_started")
    except Exception as e:
        logger.error("health_monitor_task_start_failed", error=str(e))
        raise

    # Startup: Start cache warming background task (best-effort)
    try:
        await cache_warming_task.start()
        logger.info("cache_warming_task_started")
    except Exception as e:
        logger.warning("cache_warming_task_start_failed", error=str(e))

    # Startup: Seed system templates (best-effort, idempotent)
    try:
        from app.db.session import async_session_maker
        from app.services.template_seeder import seed_system_templates
        async with async_session_maker() as db:
            inserted = await seed_system_templates(db)
        logger.info("template_seeding_completed", inserted=inserted)
    except Exception as e:
        logger.warning("template_seeding_failed", error=str(e))

    yield

    # Shutdown: Stop cache warming task
    try:
        await cache_warming_task.stop()
        logger.info("cache_warming_task_stopped")
    except Exception as e:
        logger.error("cache_warming_task_stop_failed", error=str(e))

    # Shutdown: Stop health monitor task
    try:
        await health_monitor_task.stop()
        logger.info("health_monitor_task_stopped")
    except Exception as e:
        logger.error("health_monitor_task_stop_failed", error=str(e))
    
    # Shutdown: Disconnect from Redis
    try:
        await redis_cache.disconnect()
        logger.info("redis_disconnected")
    except Exception as e:
        logger.error("redis_disconnect_failed", error=str(e))
    
    logger.info("application_shutdown_completed")


app = FastAPI(
    title="AI Presentation Intelligence Platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware (order matters — outermost first, i.e. added last wraps all)
# ---------------------------------------------------------------------------

# Security headers + HTTPS enforcement (outermost — applied to every response)
app.add_middleware(SecurityHeadersMiddleware)

# API versioning — injects API-Version header, handles deprecated/sunset versions
app.add_middleware(APIVersioningMiddleware)

# CORS — uses explicit CORS_ORIGINS whitelist from settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "Last-Event-ID"],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "API-Version",
        "Deprecation",
        "Sunset",
    ],
)

# Audit logging — records all mutations and sensitive reads
app.add_middleware(AuditMiddleware)

# Sanitize inputs before RBAC so clean data reaches route handlers
app.add_middleware(SanitizationMiddleware)

# Set tenant context (request.state.tenant_id) before DB sessions open
app.add_middleware(TenantMiddleware)

# RBAC enforcement at ASGI level (defence-in-depth; fine-grained deps in routes)
app.add_middleware(RBACMiddleware)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router, prefix="/api/v1")
app.include_router(presentations_router, prefix="/api/v1")
app.include_router(slide_editing_router, prefix="/api/v1")
# Export, templates, prompts, and cache endpoints
app.include_router(export_templates_admin_router, prefix="/api/v1")
# Internal admin-only endpoints (provider management)
app.include_router(internal_admin_router, prefix="/internal")
# Health check endpoints (30.5)
app.include_router(health_router)
# Schema versioning endpoints (31.5)
app.include_router(schema_versioning_router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# API versioning endpoint (20.5)
# ---------------------------------------------------------------------------


@app.get("/api/versions", tags=["versioning"])
async def api_versions():
    """
    List all API versions, their status, and deprecation/sunset dates.
    """
    return JSONResponse(content=get_api_versions_response())
