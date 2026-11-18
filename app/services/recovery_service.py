import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.job import Job, JobStatus
from app.models.outbox_event import OutboxEvent
from app.services import outbox_service

OUTBOX_RETENTION_DAYS = 7


def recover_stale_jobs() -> list[tuple[uuid.UUID, str, str | None]]:
    """Find jobs whose worker died and either re-queue them or fail them.

    A job is stale when it is PROCESSING but has not reported progress for longer than
    any task could legitimately run. Returns (job_id, new_status, error) for each change.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=settings.STALE_JOB_MINUTES)
    changes: list[tuple[uuid.UUID, str, str | None]] = []

    with SessionLocal() as db:
        stale = db.scalars(
            select(Job)
            .where(
                Job.status == JobStatus.PROCESSING.value,
                func.coalesce(Job.heartbeat_at, Job.started_at, Job.created_at) < cutoff,
            )
            .with_for_update(skip_locked=True)
        ).all()

        for job in stale:
            if job.retry_count >= settings.JOB_MAX_RETRIES:
                job.status = JobStatus.FAILED.value
                job.current_stage = "Failed"
                job.error_message = "The worker stopped responding and the retry limit was reached"
                job.completed_at = now
                changes.append((job.id, job.status, job.error_message))
            else:
                job.status = JobStatus.RETRYING.value
                job.retry_count += 1
                job.current_stage = "Recovered after worker failure"
                job.error_message = "The worker stopped responding; the job was re-queued"
                outbox_service.enqueue_event(db, job.id)
                changes.append((job.id, job.status, None))


        db.execute(
            delete(OutboxEvent).where(
                OutboxEvent.sent_at < now - timedelta(days=OUTBOX_RETENTION_DAYS)
            )
        )
        db.commit()
    return changes