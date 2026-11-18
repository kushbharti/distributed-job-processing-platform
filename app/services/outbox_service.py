import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.job import Job, JobStatus
from app.models.outbox_event import OutboxEvent
from app.tasks.celery_app import celery_app
from app.websocket.events import publish_job_event

logger = logging.getLogger(__name__)

PROCESS_TASK = "jobs.process_document"


def enqueue_event(db: Session, job_id: uuid.UUID) -> None:
    """Record the intent to publish. Does NOT commit: the caller commits it with the job."""
    db.add(OutboxEvent(job_id=job_id, task_name=PROCESS_TASK))


def dispatch_pending(limit: int = 20, job_id: uuid.UUID | None = None) -> int:
    """Publish unsent events to the broker. Safe to call from many processes at once."""
    sent = 0
    queued: list[uuid.UUID] = []
    with SessionLocal() as db:
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.sent_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        if job_id is not None:
            stmt = stmt.where(OutboxEvent.job_id == job_id)

        for event in db.scalars(stmt).all():
            try:
                celery_app.send_task(
                    event.task_name, args=[str(event.job_id)], task_id=str(event.job_id)
                )
            except Exception as exc:
                event.attempts += 1
                event.last_error = f"{type(exc).__name__}: {exc}"[:500]
                logger.warning("Outbox publish failed for job %s", event.job_id, exc_info=True)
                break

            event.sent_at = func.now()
            moved = db.execute(
                update(Job)
                .where(Job.id == event.job_id, Job.status == JobStatus.PENDING.value)
                .values(status=JobStatus.QUEUED.value, current_stage="Queued")
            )
            if moved.rowcount == 1:
                queued.append(event.job_id)
            sent += 1
        db.commit()

    for queued_id in queued:
        publish_job_event(queued_id, JobStatus.QUEUED.value, 0, "Queued")
    return sent