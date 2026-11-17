import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, 
    DateTime, 
    ForeignKey, 
    Index, 
    Integer, 
    String, 
    Uuid, 
    func
    )

from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentStatus:
    UPLOADED = "UPLOADED"
    

class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
       Index("ix_documents_user_id_created_at", "user_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(BigInteger)
    content_type: Mapped[str] = mapped_column(String(100))
    page_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(20), default=DocumentStatus.UPLOADED, server_default=DocumentStatus.UPLOADED
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )