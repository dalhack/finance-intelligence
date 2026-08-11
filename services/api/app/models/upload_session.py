from datetime import datetime
from uuid import UUID, uuid4

from app.db.base import Base
from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False, default="document.bin")
    sanitized_filename: Mapped[str] = mapped_column(String(255), nullable=False, default="document.bin")
    normalized_extension: Mapped[str] = mapped_column(String(20), nullable=False, default=".bin")
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    declared_mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    classification: Mapped[str] = mapped_column(String(50), nullable=False, default="CONFIDENTIAL")
    expected_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    received_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    server_computed_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_UPLOAD")
    temporary_object_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
