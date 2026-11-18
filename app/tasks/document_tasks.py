import logging
import uuid

from sqlalchemy import select

import app.models  # noqa: F401  (registers all models for this process)
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.job import Job
from app.services import job_state
from app.services.pdf_service import PDFProcessingError
from app.services.processing_service import remove_outputs, run_pipeline
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


class JobCancelledError(Exception):
    pass


@celery_app.task(name="jobs.process_document", bind=True)
def process_document(self, job_id: str) -> dict:
    job_uuid = uuid.UUID(job_id)

    # Step 1: claim the job and read what we need, then free the connection.
    with SessionLocal() as db:
        if not job_state.claim_job(db, job_uuid):
            logger.info("Job %s not claimable (cancelled, done or taken); skipping", job_id)
            return {"skipped": True}
        row = db.execute(
            select(Document.file_path, Document.filename)
            .join(Job, Job.document_id == Document.id)
            .where(Job.id == job_uuid)
        ).first()

    if row is None:
        job_state.fail_job(job_uuid, "Document not found")
        return {"failed": "Document not found"}
    file_path, filename = row

    # Step 2: progress callback = database write + cancellation check.
    def on_progress(stage: str, progress: int) -> None:
        if not job_state.update_progress(job_uuid, stage, progress):
            raise JobCancelledError

    # Step 3: run the pipeline and record the outcome.
    try:
        output = run_pipeline(
            source_relative_path=file_path,
            original_filename=filename,
            output_key=job_id,
            on_progress=on_progress,
        )
    except JobCancelledError:
        remove_outputs(job_id)
        return {"cancelled": True}
    except PDFProcessingError as exc:  # permanent: the file itself is bad
        job_state.fail_job(job_uuid, str(exc))
        return {"failed": str(exc)}
    except Exception:  # unexpected: record it, then let Celery log the traceback
        job_state.fail_job(job_uuid, "Unexpected processing error")
        raise

    if not job_state.complete_job(job_uuid, output):
        # Cancelled in the final moments: don't leave orphan files behind.
        remove_outputs(job_id)
        return {"cancelled": True}
    return {"status": "COMPLETED"}