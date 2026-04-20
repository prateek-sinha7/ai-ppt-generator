"""
Celery application configuration with three queues:
- high-priority: presentation generation jobs
- default: slide regeneration and general tasks
- export: PPTX export jobs
"""
from kombu import Exchange, Queue

from celery import Celery

from app.core.config import settings

# ---------------------------------------------------------------------------
# Queue / exchange definitions (15.1)
# ---------------------------------------------------------------------------

high_priority_exchange = Exchange("high-priority", type="direct")
default_exchange = Exchange("default", type="direct")
export_exchange = Exchange("export", type="direct")

TASK_QUEUES = (
    Queue("high-priority", high_priority_exchange, routing_key="high-priority"),
    Queue("default", default_exchange, routing_key="default"),
    Queue("export", export_exchange, routing_key="export"),
)

TASK_ROUTES = {
    "generate_presentation": {"queue": "high-priority", "routing_key": "high-priority"},
    "regenerate_slide": {"queue": "default", "routing_key": "default"},
    "export_pptx": {"queue": "export", "routing_key": "export"},
}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

celery_app = Celery(
    "ai_presentation_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_queues=TASK_QUEUES,
    task_routes=TASK_ROUTES,
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    # Reliability settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Result expiry: 24 hours
    result_expires=86400,
)
