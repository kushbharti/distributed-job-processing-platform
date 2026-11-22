import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column,relationship

from app.db.base import Base
from app.models.document import Document

class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# States in which a job still has work to do.
ACTIVE_STATUSES = (
    JobStatus.PENDING.value,
    JobStatus.QUEUED.value,
    JobStatus.PROCESSING.value,
    JobStatus.RETRYING.value,
)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_user_id_created_at", "user_id", "created_at"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_celery_task_id", "celery_task_id"),
        Index(
            "uq_jobs_active_document",
            "document_id",
            unique=True,
            postgresql_where=text(
                "status IN ('PENDING','QUEUED','PROCESSING','RETRYING')"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE")
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(20),
        default=JobStatus.PENDING.value,
        server_default=JobStatus.PENDING.value,
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    current_stage: Mapped[str | None] = mapped_column(String(100))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    document: Mapped[Document] = relationship()

    @property
    def document_filename(self) -> str | None:
        return self.document.filename if self.document is not None else None