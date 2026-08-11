from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.db.base import Base
from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class CalculationReconciliation(Base):
    __tablename__ = "calculation_reconciliations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    calculation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_reported_fact_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_reported_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 6), nullable=True)
    system_derived_value: Mapped[Decimal] = mapped_column(
        Numeric(28, 6), nullable=False
    )  # @deprecated -> derived_unrounded_value
    derived_unrounded_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 10), nullable=True)
    difference: Mapped[Decimal | None] = mapped_column(
        Numeric(28, 6), nullable=True
    )  # @deprecated -> absolute_difference
    absolute_difference: Mapped[Decimal] = mapped_column(Numeric(38, 10), nullable=False, default=Decimal("0.0"))
    relative_difference: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    tolerance: Mapped[Decimal] = mapped_column(Numeric(28, 6), nullable=False, default=Decimal("0.05"))
    applied_tolerance_kind: Mapped[str | None] = mapped_column(String(50), nullable=True)
    applied_tolerance_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 6), nullable=True)
    applied_tolerance_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tolerance_policy_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reconciliation_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reconciled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
