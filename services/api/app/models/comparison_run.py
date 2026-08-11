from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.db.base import Base
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.result_dataset_model import ResultDatasetModel


class ComparisonRun(Base):
    __tablename__ = "comparison_runs"
    __table_args__ = (UniqueConstraint("organization_id", "id", name="uq_comparison_runs_tenant_id"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    comparison_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    value_source_policy: Mapped[str] = mapped_column(String(50), nullable=False)
    query_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    result_dataset: Mapped["ResultDatasetModel | None"] = relationship(
        "ResultDatasetModel",
        back_populates="comparison_run",
        uselist=False,
    )
