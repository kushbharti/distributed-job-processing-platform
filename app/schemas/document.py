import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.job import JobStatus


class DocumentJobRef(BaseModel):
    id: uuid.UUID
    status: JobStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    file_size: int
    content_type: str
    page_count: int | None
    status: str
    created_at: datetime
    latest_job: DocumentJobRef | None = None


class DocumentList(BaseModel):
    items: list[DocumentRead]
    total: int
    limit: int
    offset: int