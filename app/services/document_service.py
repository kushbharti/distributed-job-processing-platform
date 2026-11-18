import logging
import uuid
from pathlib import Path

import pymupdf
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.job import ACTIVE_STATUSES, Job
from app.models.job_result import JobResult

logger = logging.getLogger(__name__)

PDF_SIGNATURE = b"%PDF-"
ALLOWED_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}
CHUNK_SIZE = 1024 * 1024  # 1 MB


class InvalidDocumentError(Exception):
    """The uploaded file is not acceptable. The message is safe to show the user."""


class FileTooLargeError(InvalidDocumentError):
    pass


class DocumentInUseError(Exception):
    pass


def _clean_filename(raw: str | None) -> str:
    # Keep only the final path component and cap the length.
    name = Path((raw or "").replace("\\", "/")).name.strip()
    return name[:255] if name else "document.pdf"


def _write_stream(upload: UploadFile, destination: Path) -> int:
    """Copy the upload to disk in chunks. Returns the size in bytes."""
    header = upload.file.read(len(PDF_SIGNATURE))
    if header != PDF_SIGNATURE:
        raise InvalidDocumentError("File is not a valid PDF")

    size = len(header)
    with open(destination, "wb") as out:
        out.write(header)
        while chunk := upload.file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > settings.max_upload_bytes:
                raise FileTooLargeError(
                    f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit"
                )
            out.write(chunk)
    return size


def _inspect_pdf(path: Path) -> int:
    """Open the file with PyMuPDF to prove it is a readable PDF. Returns page count."""
    try:
        data = path.read_bytes()
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise InvalidDocumentError("Password-protected PDFs are not supported")
            if pdf.page_count == 0:
                raise InvalidDocumentError("PDF has no pages")
            return pdf.page_count
    except InvalidDocumentError:
        raise
    except Exception:
        raise InvalidDocumentError("PDF is corrupted or unreadable") from None

def _remove_quietly(path: Path) -> None:
    """Best-effort cleanup: a failure here must never hide the original error."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not remove %s", path, exc_info=True)


def save_upload(db: Session, user_id: uuid.UUID, upload: UploadFile) -> Document:
    original_name = _clean_filename(upload.filename)
    if not original_name.lower().endswith(".pdf"):
        raise InvalidDocumentError("Only .pdf files are allowed")
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise InvalidDocumentError("Content type must be application/pdf")

    document_id = uuid.uuid4()
    stored_filename = f"{document_id}.pdf"
    relative_path = Path("documents") / stored_filename
    absolute_path = settings.upload_path / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        size = _write_stream(upload, absolute_path)
        page_count = _inspect_pdf(absolute_path)
        document = Document(
            id=document_id,
            user_id=user_id,
            filename=original_name,
            stored_filename=stored_filename,
            file_path=relative_path.as_posix(),
            file_size=size,
            content_type="application/pdf",
            page_count=page_count,
        )
        db.add(document)
        db.commit()
    except Exception:
     
        db.rollback()
        _remove_quietly(absolute_path)
        raise

    db.refresh(document)
    return document


def list_documents(
    db: Session, user_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[Document], int]:
    base = select(Document).where(Document.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = db.scalars(
        base.order_by(Document.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return list(items), total


def get_document(
    db: Session, user_id: uuid.UUID, document_id: uuid.UUID
) -> Document | None:
 
    return db.scalar(
        select(Document).where(
            Document.id == document_id, Document.user_id == user_id
        )
    )


def delete_document(db: Session, document: Document) -> None:
    active = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.document_id == document.id, Job.status.in_(ACTIVE_STATUSES))
    )
    if active:
        raise DocumentInUseError("Document has a job in progress. Cancel it first.")

    # Collect result files BEFORE the rows disappear.
    result_files = db.execute(
        select(JobResult.extracted_text_path, JobResult.report_path)
        .join(Job, Job.id == JobResult.job_id)
        .where(Job.document_id == document.id)
    ).all()
    relative_paths = [document.file_path, *[p for row in result_files for p in row]]

    db.delete(document)  # the database cascades to jobs and job_results
    db.commit()

    # Files go last: an orphan file is better than a row pointing at nothing.
    for relative in relative_paths:
        absolute = (settings.upload_path / relative).resolve()
        if absolute.is_relative_to(settings.upload_path):
            absolute.unlink(missing_ok=True)