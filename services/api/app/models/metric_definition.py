from datetime import date, datetime
from uuid import UUID, uuid4

from app.db.base import Base
from sqlalchemy import Date, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(50), nullable=False, default="CURRENCY")
    default_currency_behavior: Mapped[str] = mapped_column(String(50), nullable=False, default="SAME_AS_SOURCE")
    default_unit: Mapped[str] = mapped_column(String(50), nullable=False, default="TRY")
    normal_balance: Mapped[str] = mapped_column(String(50), nullable=False, default="NOT_APPLICABLE")
    aggregation_behavior: Mapped[str] = mapped_column(String(50), nullable=False, default="POINT_IN_TIME")
    formula_type: Mapped[str] = mapped_column(String(50), nullable=False, default="SOURCE_REPORTED")
    formula_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    numerator_metric_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    denominator_metric_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
