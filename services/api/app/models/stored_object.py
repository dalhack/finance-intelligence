from datetime import datetime
from uuid import UUID, uuid4

from app.db.base import Base
from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class StoredObject(Base):
    __tablename__ = "stored_objects"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    opaque_object_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    storage_bucket_alias: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    server_computed_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    detected_mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    integrity_status: Mapped[str] = mapped_column(String(50), nullable=False, default="VALIDATED")
    retention_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    deletion_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    reference_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
