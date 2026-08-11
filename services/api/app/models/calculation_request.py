from datetime import datetime
from uuid import UUID, uuid4

from app.db.base import Base
from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class CalculationRequest(Base):
    __tablename__ = "calculation_requests"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    formula_code: Mapped[str] = mapped_column(String(100), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    institution_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    reporting_period_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    comparison_period_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    comparison_policy: Mapped[str] = mapped_column(String(50), nullable=False, default="PREVIOUS_PERIOD")
    requested_by_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
