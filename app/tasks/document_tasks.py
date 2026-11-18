import logging
import time
import uuid

from celery.exceptions import SoftTimeLimitExceeded
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

import app.models  # noqa: F401  (registers all models for this process)
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.job import Job
from app.services import job_state
from app.services.pdf_service import PDFProcessingError
from app.services.processing_service import remove_outputs, run_pipeline
from app.services.reliability import backoff_seconds
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Temporary problems: repeating the same work a little later may well succeed.
# Everything else (PDFProcessingError, bugs) is treated as permanent.
TRANSIENT_ERRORS = (OperationalError, RedisError, OSError)


class JobCancelledError(Exception):
    pass


def _dev_delay() -> None:
    if settings.DEV_STAGE_DELAY_SECONDS and not settings.is_production:
        time.sleep(settings.DEV_STAGE_DELAY_SECONDS)


def _retry_or_fail(task, job_uuid: uuid.UUID, retry_count: int, exc: Exception) -> dict:
    if retry_count >= settings.JOB_MAX_RETRIES:
        job_state.fail_job(
            job_uuid, f"Failed after {retry_count} retries ({type(exc).__name__})"
        )
        return {"failed": "retries exhausted"}

    delay = backoff_seconds(retry_count)
    message = (
        f"Temporary error ({type(exc).__name__}); retry {retry_count + 1} of "
        f"{settings.JOB_MAX_RETRIES} in about {round(delay)}s"
    )
    # If the database is down this raises, the job stays PROCESSING and the
    # recovery sweep takes over once heartbeats go stale.
    if not job_state.mark_retrying(job_uuid, message):
        return {"cancelled": True}
    logger.warning("Job %s: %s", job_uuid, message, exc_info=exc)
    raise task.retry(exc=exc, countdown=delay)


@celery_app.task(name="jobs.process_document", bind=True, max_retries=None)
def process_document(self, job_id: str) -> dict:
    job_uuid = uuid.UUID(job_id)

    # Phase 1: claim the job and read what we need, then release the connection.
    try:
        with SessionLocal() as db:
            retry_count = job_state.claim_job(db, job_uuid)
            row = None
            if retry_count is not None:
                row = db.execute(
                    select(Document.file_path, Document.filename)
                    .join(Job, Job.document_id == Document.id)
                    .where(Job.id == job_uuid)
                ).first()
    except TRANSIENT_ERRORS as exc:
        # Nothing was changed yet, so a plain Celery retry is safe.
        if self.request.retries >= settings.JOB_MAX_RETRIES:
            raise
        raise self.retry(exc=exc, countdown=backoff_seconds(self.request.retries)) from exc

    if retry_count is None:
        logger.info("Job %s not claimable (cancelled, finished or taken); skipping", job_id)
        return {"skipped": True}
    if row is None:
        job_state.fail_job(job_uuid, "Document not found")
        return {"failed": "Document not found"}
    file_path, filename = row

    # Phase 2: progress callback = database write + heartbeat + cancellation check.
    def on_progress(stage: str, progress: int) -> None:
        if not job_state.update_progress(job_uuid, stage, progress):
            raise JobCancelledError
        _dev_delay()

    # Phase 3: run the pipeline and record the outcome.
    try:
        output = run_pipeline(
            source_relative_path=file_path,
            original_filename=filename,
            output_key=job_id,
            on_progress=on_progress,
        )
        if not job_state.complete_job(job_uuid, output):
            remove_outputs(job_id)  # cancelled in the final moments
            return {"cancelled": True}
    except JobCancelledError:
        remove_outputs(job_id)
        return {"cancelled": True}
    except PDFProcessingError as exc:  # permanent: the file itself is bad
        job_state.fail_job(job_uuid, str(exc))
        return {"failed": str(exc)}
    except SoftTimeLimitExceeded:
        job_state.fail_job(job_uuid, "Processing timed out")
        return {"failed": "timeout"}
    except TRANSIENT_ERRORS as exc:
        return _retry_or_fail(self, job_uuid, retry_count, exc)
    except Exception:
        job_state.fail_job(job_uuid, "Unexpected processing error")
        raise  # the traceback goes to the worker log; users only see the generic message

    return {"status": "COMPLETED"}