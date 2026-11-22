import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.job import ACTIVE_STATUSES, Job, JobStatus
from app.models.job_result import JobResult
from app.services import document_service, outbox_service
from app.websocket.events import publish_job_event

logger = logging.getLogger(__name__)


class DocumentNotFoundError(Exception):
    pass


class ActiveJobExistsError(Exception):
    pass


class JobNotCancellableError(Exception):
    pass


class JobNotRetryableError(Exception):
    pass


class JobNotFinishedError(Exception):
    pass


def _dispatch_best_effort(job_id: uuid.UUID) -> None:
    """Try to publish right away. If that fails, the outbox poller delivers it later."""
    try:
        outbox_service.dispatch_pending(job_id=job_id)
    except Exception:
        logger.exception("Immediate dispatch failed for job %s; the poller will retry", job_id)


def create_job(db: Session, user_id: uuid.UUID, document_id: uuid.UUID) -> Job:
    # Ownership check: someone else's document looks like "not found".
    if document_service.get_document(db, user_id, document_id) is None:
        raise DocumentNotFoundError

    job_id = uuid.uuid4()
    job = Job(id=job_id, user_id=user_id, document_id=document_id, celery_task_id=str(job_id))
    try:
        db.add(job)
        db.flush()  # the job row must exist before the outbox row that references it
        outbox_service.enqueue_event(db, job_id)
        db.commit()  # job + outbox intent saved atomically
    except IntegrityError:
        db.rollback()
        raise ActiveJobExistsError from None

    _dispatch_best_effort(job_id)
    db.refresh(job)
    return job


def retry_job(db: Session, job: Job) -> Job:
    """Manual reprocessing: FAILED or CANCELLED -> PENDING, then dispatched via the outbox."""
    try:
        result = db.execute(
            update(Job)
            .where(
                Job.id == job.id,
                Job.status.in_([JobStatus.FAILED.value, JobStatus.CANCELLED.value]),
            )
            .values(
                status=JobStatus.PENDING.value,
                progress=0,
                current_stage="Waiting to be queued",
                error_message=None,
                retry_count=0,
                started_at=None,
                completed_at=None,
                heartbeat_at=None,
            )
        )
        if result.rowcount == 0:
            db.rollback()
            raise JobNotRetryableError
        outbox_service.enqueue_event(db, job.id)
        db.commit()
    except IntegrityError:
        # Another job for this document is active (partial unique index).
        db.rollback()
        raise ActiveJobExistsError from None

    _dispatch_best_effort(job.id)
    db.refresh(job)
    return job


def get_job(db: Session, user_id: uuid.UUID, job_id: uuid.UUID) -> Job | None:
    return db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))


def list_jobs(
    db: Session,
    user_id: uuid.UUID,
    *,
    statuses: list[JobStatus] | None,
    document_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Job], int]:
    conditions = [Job.user_id == user_id]
    if statuses:
        conditions.append(Job.status.in_([s.value for s in statuses]))
    if document_id is not None:
        conditions.append(Job.document_id == document_id)

    total = db.scalar(select(func.count()).select_from(Job).where(*conditions)) or 0
    items = db.scalars(
        select(Job)
        .options(joinedload(Job.document))  # file names in the same query, not one query per row
        .where(*conditions)
        .order_by(Job.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(items), total

def job_stats(db: Session, user_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(
        select(Job.status, func.count()).where(Job.user_id == user_id).group_by(Job.status)
    ).all()
    counts = {status.value: 0 for status in JobStatus}  # every status is present, even at zero
    counts.update({status: count for status, count in rows})
    return counts

def cancel_job(db: Session, job: Job) -> Job:
    result = db.execute(
        update(Job)
        .where(Job.id == job.id, Job.status.in_(ACTIVE_STATUSES))
        .values(
            status=JobStatus.CANCELLED.value,
            current_stage="Cancelled",
            completed_at=func.now(),
        )
    )
    db.commit()
    if result.rowcount == 0:
        raise JobNotCancellableError
    db.refresh(job)
    publish_job_event(job.id, job.status, job.progress, job.current_stage)
    return job


def get_result(db: Session, job: Job) -> JobResult:
    if job.status != JobStatus.COMPLETED.value:
        raise JobNotFinishedError
    result = db.scalar(select(JobResult).where(JobResult.job_id == job.id))
    if result is None:
        raise JobNotFinishedError
    return result