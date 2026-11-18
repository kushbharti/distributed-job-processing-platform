import uuid

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.job import Job, JobStatus
from app.models.job_result import JobResult

PROCESSING = JobStatus.PROCESSING.value
CLAIMABLE = (
    JobStatus.PENDING.value,
    JobStatus.QUEUED.value,
    JobStatus.RETRYING.value,
)
NOT_FINISHED = (*CLAIMABLE, PROCESSING)


def claim_job(db: Session, job_id: uuid.UUID) -> int | None:
    """Atomically move a claimable job to PROCESSING.

    Returns the job's retry_count for the one worker that wins, or None for everyone else
    (job cancelled, already finished, or being processed by another worker).
    """
    row = db.execute(
        update(Job)
        .where(Job.id == job_id, Job.status.in_(CLAIMABLE))
        .values(
            status=PROCESSING,
            started_at=func.now(),
            heartbeat_at=func.now(),
            progress=0,
            current_stage="Starting",
        )
        .returning(Job.retry_count)
        .execution_options(synchronize_session=False)
    ).first()
    db.commit()
    return None if row is None else row[0]


def update_progress(job_id: uuid.UUID, stage: str, progress: int) -> bool:
    """Record progress and a heartbeat. False means the job is no longer PROCESSING."""
    with SessionLocal() as db:
        result = db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == PROCESSING)
            .values(current_stage=stage, progress=progress, heartbeat_at=func.now())
        )
        db.commit()
        return result.rowcount == 1


def mark_retrying(job_id: uuid.UUID, message: str) -> bool:
    with SessionLocal() as db:
        result = db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == PROCESSING)
            .values(
                status=JobStatus.RETRYING.value,
                retry_count=Job.retry_count + 1,
                current_stage="Waiting to retry",
                error_message=message[:1000],
            )
        )
        db.commit()
        return result.rowcount == 1


def complete_job(job_id: uuid.UUID, output: dict) -> bool:
    """Mark COMPLETED and store the result in ONE transaction."""
    with SessionLocal() as db:
        updated = db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == PROCESSING)
            .values(
                status=JobStatus.COMPLETED.value,
                progress=100,
                current_stage="Completed",
                completed_at=func.now(),
                error_message=None,
            )
        )
        if updated.rowcount != 1:
            db.rollback()
            return False
        db.add(
            JobResult(
                job_id=job_id,
                extracted_text_path=output["extracted_text_path"],
                report_path=output["report_path"],
                summary=output["summary"],
                keywords=output["keywords"],
                stats=output["stats"],
                pdf_metadata=output["metadata"],
            )
        )
        db.commit()
        return True


def fail_job(job_id: uuid.UUID, message: str) -> None:
    with SessionLocal() as db:
        db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status.in_(NOT_FINISHED))
            .values(
                status=JobStatus.FAILED.value,
                current_stage="Failed",
                error_message=message[:1000],
                completed_at=func.now(),
            )
        )
        db.commit()