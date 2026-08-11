from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.db.base import Base
from sqlalchemy import DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class CandidateEvidence(Base):
    __tablename__ = "candidate_evidence"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    candidate_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_document_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sheet_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    cell_coordinate: Mapped[str | None] = mapped_column(Text, nullable=True)
    header_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    column_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bounding_box: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    raw_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
