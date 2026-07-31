from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from services.api.app.schemas.result_dataset import (
    ChartSpecDTO,
    ResultDatasetDTO,
    TableSpecDTO,
)


class SemanticMeasureSelectorDTO(BaseModel):
    """Explicit selector for canonical semantic measure and preferred origin."""

    model_config = ConfigDict(extra="forbid")

    semantic_measure_code: str
    preferred_origin: Literal["AUTO", "SOURCE_REPORTED", "SYSTEM_DERIVED"] = "AUTO"


class ComparisonRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution_ids: list[UUID] = Field(min_length=1, max_length=10)
    semantic_measures: list[SemanticMeasureSelectorDTO] = Field(min_length=1, max_length=15)
    reporting_period_ids: list[UUID] = Field(min_length=1, max_length=20)
    reporting_basis: Literal["SOLO", "CONSOLIDATED"]
    currency: str = "TRY"
    display_scale: Literal["ONE", "THOUSAND", "MILLION", "BILLION"] = "MILLION"
    value_source_policy: Literal[
        "SOURCE_REPORTED_ONLY",
        "SYSTEM_DERIVED_ONLY",
        "PREFER_SOURCE_REPORTED",
        "PREFER_SYSTEM_DERIVED",
        "BOTH_SEPARATE_SERIES",
    ] = "PREFER_SOURCE_REPORTED"
    sort_measure_code: str | None = None
    sort_origin: Literal["SOURCE_REPORTED", "SYSTEM_DERIVED"] | None = None
    sort_direction: Literal["asc", "desc"] = "desc"
    top_n: int | None = Field(default=None, ge=1, le=50)
    top_n_scope: Literal["INSTITUTIONS_PER_PERIOD", "DATASET_ROWS_GLOBAL"] = "INSTITUTIONS_PER_PERIOD"
    comparison_mode: Literal["PERIOD_OVER_PERIOD", "CROSS_INSTITUTION", "MULTI_METRIC"] = "CROSS_INSTITUTION"
    common_period_policy: Literal["STRICT_COMMON_PERIOD", "ALLOW_PARTIAL_WITH_WARNINGS"] = "ALLOW_PARTIAL_WITH_WARNINGS"
    evidence_policy: Literal["STRICT", "PARTIAL"] = "PARTIAL"
    chart_types: list[Literal["horizontal_bar", "vertical_bar", "grouped_bar", "line"]] = Field(
        default=["vertical_bar", "line"],
        max_length=4,
    )
    include_evidence: bool = True
    include_reconciliation: bool = True
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ComparisonResponseDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparison_id: UUID
    result_dataset: ResultDatasetDTO
    table_spec: TableSpecDTO
    chart_specs: list[ChartSpecDTO]


class ComparisonFiltersDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supported_institutions: list[dict[str, str]]
    supported_reporting_periods: list[dict[str, str]]
    supported_semantic_measures: list[dict[str, str]]
    supported_reporting_bases: list[str]
    supported_currencies: list[str]
    supported_scales: list[str]
    supported_source_policies: list[str]
    supported_chart_types: list[str]
    supported_top_n_scopes: list[str]
    supported_common_period_policies: list[str]
    supported_evidence_policies: list[str]
    is_data_backed: bool = True


class EvidenceDetailDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID
    document_title: str | None = None
    document_version_id: UUID
    mime_type: str | None = None
    mime_verified: bool = False
    page_number: int | None = None
    sheet_name: str | None = None
    cell_coordinate: str | None = None
    row_index: int | None = None
    column_index: int | None = None
    bounding_box: dict[str, Any] | None = None
    sanitized_snippet: str | None = None
    extraction_method: str | None = None
    confidence_score: str | None = None
    review_status: str | None = None
    source_authority: str | None = None
    classification: str = "CONFIDENTIAL"
    is_masked: bool = False
