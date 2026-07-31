from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from services.api.app.db.base import Base


class FinancialFactCandidate(Base):
    __tablename__ = "financial_fact_candidates"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    institution_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    reporting_period_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    metric_definition_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    suggested_metric_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_label: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_value: Mapped[str] = mapped_column(String(255), nullable=False)
    parsed_decimal_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 6), nullable=True)
    raw_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="TRY")
    raw_unit: Mapped[str] = mapped_column(String(50), nullable=False, default="CURRENCY")
    raw_scale: Mapped[str] = mapped_column(String(50), nullable=False, default="ONE")
    normalized_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="TRY")
    normalized_unit: Mapped[str] = mapped_column(String(50), nullable=False, default="CURRENCY")
    normalized_scale: Mapped[str] = mapped_column(String(50), nullable=False, default="ONE")
    normalized_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 6), nullable=True)
    detected_reporting_basis: Mapped[str] = mapped_column(String(50), nullable=False, default="UNKNOWN")
    source_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_document_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_page_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_chunk_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_location: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False, default="PARSER_TABLE")
    mapping_rule_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, default=Decimal("0.500"))
    validation_status: Mapped[str] = mapped_column(String(50), nullable=False, default="EXTRACTED")
    review_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    warning_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    idempotency_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value_origin: Mapped[str] = mapped_column(String(32), nullable=False, default="SOURCE_REPORTED")
    conflicting_fact_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    conflict_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    conflict_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    detected_value_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
