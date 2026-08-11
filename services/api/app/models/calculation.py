from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.db.base import Base
from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, synonym


class Calculation(Base):
    __tablename__ = "calculations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    calculation_request_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    calculation_attempt_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    institution_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    reporting_period_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    comparison_period_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    formula_code: Mapped[str] = mapped_column(String(100), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="COMPLETED")
    result_value: Mapped[Decimal | None] = mapped_column(
        Numeric(28, 6), nullable=True
    )  # @deprecated -> result_value_display
    result_value_unrounded: Mapped[Decimal | None] = mapped_column(Numeric(38, 10), nullable=True)
    result_value_display: Mapped[Decimal | None] = mapped_column(Numeric(28, 6), nullable=True)
    result_unit: Mapped[str] = mapped_column(String(50), nullable=False, default="PERCENT")
    result_scale: Mapped[str] = mapped_column(String(50), nullable=False, default="ONE")
    result_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    value_representation: Mapped[str] = mapped_column(String(50), nullable=False, default="PERCENT_DISPLAY")
    working_precision: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    rounding_policy: Mapped[str] = mapped_column(String(50), nullable=False, default="ROUND_HALF_UP")
    rounding_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="ROUND_HALF_UP")
    display_scale: Mapped[str] = mapped_column(String(50), nullable=False, default="ONE")
    calculation_precision: Mapped[int] = mapped_column(Integer, nullable=False, default=38)
    calculation_rounding_policy_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    idempotency_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_idempotency_hash = synonym("idempotency_hash")
    implementation_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    formula_spec_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    annualization_factor: Mapped[Decimal | None] = mapped_column(Numeric(28, 6), nullable=True)
    annualization_policy_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parent_calculation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    requested_by_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
