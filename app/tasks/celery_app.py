from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "job_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.document_tasks", "app.tasks.maintenance_tasks"],
)

celery_app.conf.update(
    # Messages are plain JSON, never pickle (pickle can execute code).
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Acknowledge AFTER the task finishes, so a crash leaves the message for redelivery.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    broker_connection_retry_on_startup=True,

    task_publish_retry_policy={
        "max_retries": 1,
        "interval_start": 0,
        "interval_step": 0.2,
        "interval_max": 0.5,
    },
    broker_transport_options={"visibility_timeout": 3600},
    
    task_soft_time_limit=settings.TASK_SOFT_TIME_LIMIT_SECONDS,
    task_time_limit=settings.TASK_TIME_LIMIT_SECONDS,
    beat_schedule={
        "dispatch-outbox": {
            "task": "maintenance.dispatch_outbox",
            "schedule": settings.OUTBOX_DISPATCH_INTERVAL_SECONDS,
            "options": {"expires": settings.OUTBOX_DISPATCH_INTERVAL_SECONDS * 2},
        },
        "recover-stale-jobs": {
            "task": "maintenance.recover_stale_jobs",
            "schedule": settings.RECOVERY_INTERVAL_SECONDS,
            "options": {"expires": settings.RECOVERY_INTERVAL_SECONDS * 2},
        },
    },
)