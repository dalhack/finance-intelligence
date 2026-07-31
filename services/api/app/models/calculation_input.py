from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from services.api.app.db.base import Base


class CalculationInput(Base):
    __tablename__ = "calculation_inputs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    calculation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    financial_fact_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    input_role: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_value_snapshot: Mapped[Decimal] = mapped_column(Numeric(28, 6), nullable=False)
    currency_snapshot: Mapped[str] = mapped_column(String(10), nullable=False)
    unit_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    scale_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    reporting_basis_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    reporting_period_id_snapshot: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    fact_revision_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    evidence_reference: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
