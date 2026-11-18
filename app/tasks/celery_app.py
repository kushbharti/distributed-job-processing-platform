from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "job_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.document_tasks"],
)

celery_app.conf.update(
    # Messages are plain JSON, never pickle (pickle can execute code).
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Report a STARTED state when a worker picks up the task.
    task_track_started=True,
    # Acknowledge the message AFTER the task finishes, not before.
    task_acks_late=True,
    # Each worker takes one message at a time (fair for long tasks).
    worker_prefetch_multiplier=1,
    # Redis results are temporary; PostgreSQL will be our permanent record.
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)