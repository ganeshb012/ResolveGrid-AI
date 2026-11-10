import logging
from celery import Celery
from backend.app.core.config import settings

logger = logging.getLogger("resolvegrid.celery")

celery_app = Celery(
    "resolvegrid",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["backend.app.tasks.worker_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
)
