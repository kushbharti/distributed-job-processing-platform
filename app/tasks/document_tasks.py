import uuid

import app.models  # noqa: F401  (registers all models for this process)
from app.db.session import SessionLocal
from app.models.document import Document
from app.services.pdf_service import PDFProcessingError
from app.services.processing_service import run_pipeline
from app.tasks.celery_app import celery_app


@celery_app.task(name="documents.process", bind=True)
def process_document(self, document_id: str) -> dict:
    # Read what we need, then release the DB connection before the slow work.
    with SessionLocal() as db:
        document = db.get(Document, uuid.UUID(document_id))
        if document is None:
            raise PDFProcessingError("Document not found")
        file_path = document.file_path
        filename = document.filename

    def report_progress(stage: str, progress: int) -> None:
        self.update_state(
            state="PROGRESS", meta={"stage": stage, "progress": progress}
        )

    return run_pipeline(
        source_relative_path=file_path,
        original_filename=filename,
        output_key=document_id,
        on_progress=report_progress,
    )