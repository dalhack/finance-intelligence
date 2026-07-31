from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from services.api.app.db.base import Base


class FormulaDefinition(Base):
    __tablename__ = "formula_definitions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    formula_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    formula_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    calculation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    required_input_roles: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    expected_metric_codes: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    result_unit: Mapped[str] = mapped_column(String(50), nullable=False, default="PERCENT")
    result_scale: Mapped[str] = mapped_column(String(50), nullable=False, default="ONE")
    rounding_policy: Mapped[str] = mapped_column(String(50), nullable=False, default="ROUND_HALF_UP")
    display_precision: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    implementation_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    formula_spec_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    implementation_revision: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    tolerance_policy_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    tolerance_kind: Mapped[str] = mapped_column(String(50), nullable=False, default="ABSOLUTE")
    tolerance_value: Mapped[Decimal] = mapped_column(Numeric(28, 6), nullable=False, default=Decimal("0.05"))
    tolerance_unit: Mapped[str] = mapped_column(String(50), nullable=False, default="PERCENTAGE_POINTS")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
