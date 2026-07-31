from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from services.api.app.db.base import Base


class FinancialFact(Base):
    __tablename__ = "financial_facts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    institution_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    reporting_period_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    metric_definition_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(28, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="TRY")
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="CURRENCY")
    scale: Mapped[str] = mapped_column(String(50), nullable=False, default="ONE")
    normalized_value: Mapped[Decimal] = mapped_column(Numeric(28, 6), nullable=False)
    reporting_basis: Mapped[str] = mapped_column(String(50), nullable=False, default="SOLO")
    source_candidate_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_location: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False, default="PARSER_TABLE")
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, default=Decimal("1.000"))
    review_status: Mapped[str] = mapped_column(String(50), nullable=False, default="HUMAN_VERIFIED")
    verified_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    supersedes_fact_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    value_origin: Mapped[str] = mapped_column(String(32), nullable=False, default="SOURCE_REPORTED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
