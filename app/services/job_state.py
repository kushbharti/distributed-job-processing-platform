import uuid

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.job import Job, JobStatus
from app.models.job_result import JobResult
from app.websocket.events import publish_job_event  # NEW

PROCESSING = JobStatus.PROCESSING.value
CLAIMABLE = (
    JobStatus.PENDING.value,
    JobStatus.QUEUED.value,
    JobStatus.RETRYING.value,
)
NOT_FINISHED = (*CLAIMABLE, PROCESSING)


def claim_job(db: Session, job_id: uuid.UUID) -> int | None:
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
    if row is None:
        return None
    publish_job_event(job_id, PROCESSING, 0, "Starting")  # NEW
    return row[0]


def update_progress(job_id: uuid.UUID, stage: str, progress: int) -> bool:
    with SessionLocal() as db:
        result = db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == PROCESSING)
            .values(current_stage=stage, progress=progress, heartbeat_at=func.now())
        )
        db.commit()
        updated = result.rowcount == 1
    if updated:
        publish_job_event(job_id, PROCESSING, progress, stage)  # NEW
    return updated


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
        updated = result.rowcount == 1
    if updated:
        publish_job_event(job_id, JobStatus.RETRYING.value, 0, "Waiting to retry", message)  # NEW
    return updated


def complete_job(job_id: uuid.UUID, output: dict) -> bool:
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
    publish_job_event(job_id, JobStatus.COMPLETED.value, 100, "Completed")  
    return True


def fail_job(job_id: uuid.UUID, message: str) -> None:
    with SessionLocal() as db:
        result = db.execute(
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
        failed = result.rowcount == 1
    if failed:
        publish_job_event(job_id, JobStatus.FAILED.value, 0, "Failed", message[:1000])  # NEW