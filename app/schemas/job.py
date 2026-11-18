import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.job import JobStatus


class JobCreate(BaseModel):
    document_id: uuid.UUID


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    status: JobStatus
    progress: int
    current_stage: str | None
    retry_count: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class JobList(BaseModel):
    items: list[JobRead]
    total: int
    limit: int
    offset: int


class JobResultRead(BaseModel):
    job_id: uuid.UUID
    summary: str
    keywords: list[str]
    stats: dict
    metadata: dict
    created_at: datetime