import uuid

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser
from app.core.config import settings
from app.db.dependencies import DbSession
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate, JobList, JobRead, JobResultRead
from app.services import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_or_404(db: DbSession, user: CurrentUser, job_id: uuid.UUID) -> Job:
    job = job_service.get_job(db, user.id, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@router.post("", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobCreate, user: CurrentUser, db: DbSession):
    try:
        return job_service.create_job(db, user.id, payload.document_id)
    except job_service.DocumentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    except job_service.ActiveJobExistsError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This document already has a job in progress"
        )


@router.get("", response_model=JobList)
def list_jobs(
    user: CurrentUser,
    db: DbSession,
    status_filter: JobStatus | None = Query(None, alias="status"),
    document_id: uuid.UUID | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    items, total = job_service.list_jobs(
        db,
        user.id,
        status=status_filter,
        document_id=document_id,
        limit=limit,
        offset=offset,
    )
    return JobList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return _job_or_404(db, user, job_id)


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(job_id: uuid.UUID, user: CurrentUser, db: DbSession):
    job = _job_or_404(db, user, job_id)
    try:
        return job_service.cancel_job(db, job)
    except job_service.JobNotCancellableError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Job has already finished and cannot be cancelled"
        )

@router.post("/{job_id}/retry", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def retry_job(job_id: uuid.UUID, user: CurrentUser, db: DbSession):
    job = _job_or_404(db, user, job_id)
    try:
        return job_service.retry_job(db, job)
    except job_service.JobNotRetryableError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Only FAILED or CANCELLED jobs can be retried"
        )
    except job_service.ActiveJobExistsError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This document already has a job in progress"
        )


@router.get("/{job_id}/result", response_model=JobResultRead)
def get_job_result(job_id: uuid.UUID, user: CurrentUser, db: DbSession):
    job = _job_or_404(db, user, job_id)
    try:
        result = job_service.get_result(db, job)
    except job_service.JobNotFinishedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Job is {job.status}, no result available"
        )
    return JobResultRead(
        job_id=job.id,
        summary=result.summary,
        keywords=result.keywords,
        stats=result.stats,
        metadata=result.pdf_metadata,
        created_at=result.created_at,
    )


def _download(db: DbSession, user: CurrentUser, job_id: uuid.UUID, attr: str,
              media_type: str, filename: str) -> FileResponse:
    job = _job_or_404(db, user, job_id)
    try:
        result = job_service.get_result(db, job)
    except job_service.JobNotFinishedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Job is {job.status}, no result available"
        )
    path = (settings.upload_path / getattr(result, attr)).resolve()
    if not path.is_relative_to(settings.upload_path) or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Result file not found")
    return FileResponse(path, media_type=media_type, filename=filename)


@router.get("/{job_id}/result/report")
def download_report(job_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return _download(db, user, job_id, "report_path", "application/pdf", f"report-{job_id}.pdf")


@router.get("/{job_id}/result/text")
def download_text(job_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return _download(db, user, job_id, "extracted_text_path", "text/plain", f"text-{job_id}.txt")