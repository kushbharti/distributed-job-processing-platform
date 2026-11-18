import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobResult(Base):
    __tablename__ = "job_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # unique=True: one result per job
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), unique=True
    )
    extracted_text_path: Mapped[str] = mapped_column(String(500))
    report_path: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list] = mapped_column(JSONB)
    stats: Mapped[dict] = mapped_column(JSONB)
    # "metadata" is a reserved attribute name on SQLAlchemy models,
    # so the attribute is pdf_metadata while the column is still called "metadata".
    pdf_metadata: Mapped[dict] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )