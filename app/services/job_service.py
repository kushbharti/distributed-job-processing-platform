import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.job import ACTIVE_STATUSES, Job, JobStatus
from app.models.job_result import JobResult
from app.services import document_service, job_state
from app.tasks.document_tasks import process_document

logger = logging.getLogger(__name__)


class DocumentNotFoundError(Exception):
    pass


class ActiveJobExistsError(Exception):
    pass


class QueueUnavailableError(Exception):
    pass


class JobNotCancellableError(Exception):
    pass


class JobNotFinishedError(Exception):
    pass


def create_job(db: Session, user_id: uuid.UUID, document_id: uuid.UUID) -> Job:
    # Ownership check: someone else's document looks like "not found".
    if document_service.get_document(db, user_id, document_id) is None:
        raise DocumentNotFoundError

    job_id = uuid.uuid4()
    job = Job(
        id=job_id,
        user_id=user_id,
        document_id=document_id,
        celery_task_id=str(job_id),
    )
    db.add(job)
    try:
        db.commit()  # 1) the job exists in PostgreSQL (status PENDING)
    except IntegrityError:
        db.rollback()
        raise ActiveJobExistsError from None

    try:
        # 2) publish to Redis, using the job ID as the Celery task ID
        process_document.apply_async(args=[str(job_id)], task_id=str(job_id))
    except Exception:
        logger.exception("Could not publish job %s to the broker", job_id)
        job_state.fail_job(job_id, "Could not queue the job; please try again")
        raise QueueUnavailableError from None

    # 3) PENDING -> QUEUED, but only if a fast worker hasn't already claimed it
    db.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.PENDING.value)
        .values(status=JobStatus.QUEUED.value, current_stage="Queued")
    )
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, user_id: uuid.UUID, job_id: uuid.UUID) -> Job | None:
    return db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))


def list_jobs(
    db: Session,
    user_id: uuid.UUID,
    *,
    status: JobStatus | None,
    document_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Job], int]:
    base = select(Job).where(Job.user_id == user_id)
    if status is not None:
        base = base.where(Job.status == status.value)
    if document_id is not None:
        base = base.where(Job.document_id == document_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = db.scalars(
        base.order_by(Job.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return list(items), total


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
    return job


def get_result(db: Session, job: Job) -> JobResult:
    if job.status != JobStatus.COMPLETED.value:
        raise JobNotFinishedError
    result = db.scalar(select(JobResult).where(JobResult.job_id == job.id))
    if result is None:
        raise JobNotFinishedError
    return result