from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from services.api.app.db.base import Base


class ReportingPeriod(Base):
    __tablename__ = "reporting_periods"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    period_type: Mapped[str] = mapped_column(String(50), nullable=False)  # YEAR, QUARTER, MONTH, DATE_POINT, TTM
    period_presentation: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="UNKNOWN"
    )  # DISCRETE_PERIOD, YEAR_TO_DATE, TRAILING_TWELVE_MONTHS, FULL_YEAR, DATE_POINT, UNKNOWN
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    comparison_key: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
