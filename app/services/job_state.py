import uuid

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.job import Job, JobStatus
from app.models.job_result import JobResult

P = JobStatus.PROCESSING.value


def claim_job(db: Session, job_id: uuid.UUID) -> bool:
    """Atomically move QUEUED/PENDING -> PROCESSING. True only for the one worker that wins."""
    result = db.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.status.in_([JobStatus.PENDING.value, JobStatus.QUEUED.value]),
        )
        .values(
            status=P,
            started_at=func.now(),
            progress=0,
            current_stage="Starting",
        )
    )
    db.commit()
    return result.rowcount == 1


def update_progress(job_id: uuid.UUID, stage: str, progress: int) -> bool:
    """Record progress. Returns False if the job is no longer PROCESSING (cancelled or deleted)."""
    with SessionLocal() as db:
        result = db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == P)
            .values(current_stage=stage, progress=progress)
        )
        db.commit()
        return result.rowcount == 1


def complete_job(job_id: uuid.UUID, output: dict) -> bool:
    """Mark COMPLETED and store the result in ONE transaction."""
    with SessionLocal() as db:
        updated = db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == P)
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
            .where(
                Job.id == job_id,
                Job.status.in_(
                    [JobStatus.PENDING.value, JobStatus.QUEUED.value, P]
                ),
            )
            .values(
                status=JobStatus.FAILED.value,
                current_stage="Failed",
                error_message=message[:1000],
                completed_at=func.now(),
            )
        )
        db.commit()