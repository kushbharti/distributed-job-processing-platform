import logging

from app.services import outbox_service, recovery_service
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="maintenance.dispatch_outbox")
def dispatch_outbox() -> int:
    return outbox_service.dispatch_pending(limit=50)


@celery_app.task(name="maintenance.recover_stale_jobs")
def recover_stale_jobs() -> int:
    changes = recovery_service.recover_stale_jobs()
    if changes:
        logger.warning("Recovered %d stale job(s): %s", len(changes), [str(c[0]) for c in changes])
    return len(changes)