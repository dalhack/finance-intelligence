from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.db.base import Base
from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    user_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="0" * 64)
    org_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="0" * 64)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="0" * 64)
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="0" * 64)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
