from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuerySnapshotDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution_ids: list[UUID]
    semantic_measures: list[dict[str, str]]
    reporting_period_ids: list[UUID]
    reporting_basis: str
    currency: str
    display_scale: str
    value_source_policy: str
    sort_measure_code: str | None = None
    sort_origin: str | None = None
    sort_direction: str = "desc"
    top_n_scope: str = "INSTITUTIONS_PER_PERIOD"
    comparison_mode: str = "CROSS_INSTITUTION"
    common_period_policy: str = "ALLOW_PARTIAL_WITH_WARNINGS"
    evidence_policy: str = "PARTIAL"
    top_n: int | None = None
    page: int = 1
    page_size: int = 20


class MeasureItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measure_code: str
    semantic_measure_code: str
    label: str
    unit: str
    currency: str | None = None
    scale: str
    value_origin: Literal["SOURCE_REPORTED", "SYSTEM_DERIVED"]
    formula_code: str | None = None


class DatasetRowCellDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measure_code: str
    semantic_measure_code: str
    canonical_value: str  # Lossless Decimal string
    display_value: str
    value_origin: Literal["SOURCE_REPORTED", "SYSTEM_DERIVED"]
    fact_id: UUID | None = None
    calculation_id: UUID | None = None
    evidence_id: UUID | None = None
    reconciliation_status: (
        Literal[
            "RECONCILED",
            "WITHIN_TOLERANCE",
            "OUTSIDE_TOLERANCE",
            "NO_SOURCE_REPORTED_COMPARISON",
            "NOT_APPLICABLE",
        ]
        | None
    ) = None
    warning_flag: bool = False
    warning_code: str | None = None


class DatasetRowDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_id: str
    institution_id: UUID
    institution_name: str
    reporting_period_id: UUID
    period_label: str
    reporting_basis: str
    cells: dict[str, DatasetRowCellDTO]


class TableColumnDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    data_type: Literal["string", "decimal", "currency", "percent"]
    alignment: Literal["left", "right", "center"] = "left"
    unit_label: str


class TableCellDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_value: str  # Lossless Decimal string
    display_text: str
    value_origin: Literal["SOURCE_REPORTED", "SYSTEM_DERIVED"]
    reconciliation_status: str | None = None
    warning_flag: bool = False
    warning_code: str | None = None
    evidence_id: UUID | None = None


class TableRowDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_id: str
    institution_name: str
    period_label: str
    cells: dict[str, TableCellDTO]


class PaginationDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int
    page_size: int
    total_rows: int
    total_pages: int
    has_next: bool
    has_previous: bool


class TableSpecDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_dataset_id: UUID
    schema_version: str = "3.0.0"
    columns: list[TableColumnDTO]
    rows: list[TableRowDTO]
    pagination: PaginationDTO


class ChartSeriesItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: str
    y: str  # Lossless Decimal string
    display_value: str
    label: str
    evidence_id: UUID | None = None
    warning_flag: bool = False
    warning_code: str | None = None


class ChartSeriesDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_name: str
    semantic_measure_code: str
    measure_code: str
    unit: str
    currency: str | None = None
    data_points: list[ChartSeriesItemDTO]


class ChartSpecDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_dataset_id: UUID
    chart_type: Literal["horizontal_bar", "vertical_bar", "grouped_bar", "line"]
    title: str
    subtitle: str | None = None
    x_axis_label: str
    y_axis_label: str
    unit: str
    currency: str | None = None
    series: list[ChartSeriesDTO]
    warning_annotations: list[str] = Field(default_factory=list)


class DataQualitySummaryDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_cells: int
    populated_cells: int
    missing_source_cells: int
    excluded_ineligible_cells: int
    excluded_mismatch_cells: int
    warning_cells: int
    source_reported_count: int
    system_derived_count: int
    reconciliation_warning_count: int
    completeness_percentage: str

    @model_validator(mode="after")
    def validate_data_quality_invariant(self) -> "DataQualitySummaryDTO":
        sum_cells = (
            self.populated_cells
            + self.missing_source_cells
            + self.excluded_ineligible_cells
            + self.excluded_mismatch_cells
        )
        if self.expected_cells != sum_cells:
            raise ValueError(f"DATA_QUALITY_INVARIANT_VIOLATED: expected ({self.expected_cells}) != sum ({sum_cells})")
        return self


class ResultDatasetDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_dataset_id: UUID
    schema_version: str = "3.0.0"
    generated_at: datetime
    query_snapshot: QuerySnapshotDTO
    value_source_policy: str
    dimensions: dict[str, Any]
    measures: list[MeasureItemDTO]
    rows: list[DatasetRowDTO]
    data_quality_summary: DataQualitySummaryDTO
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    evidence_references: list[UUID] = Field(default_factory=list)
    calculation_references: list[UUID] = Field(default_factory=list)
    pagination: PaginationDTO
