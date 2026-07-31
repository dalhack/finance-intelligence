from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.api.app.db.base import Base

if TYPE_CHECKING:
    from services.api.app.models.comparison_run import ComparisonRun


class ResultDatasetModel(Base):
    __tablename__ = "result_datasets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "comparison_run_id"],
            ["comparison_runs.organization_id", "comparison_runs.id"],
            name="fk_result_datasets_comparison_run",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    comparison_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    query_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    dimensions_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    measures_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rows_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    table_spec_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    chart_specs_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    data_quality_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    warnings_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    comparison_run: Mapped["ComparisonRun"] = relationship(
        "ComparisonRun",
        back_populates="result_dataset",
    )
