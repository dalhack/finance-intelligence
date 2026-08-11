from uuid import UUID

from app.core.errors import BaseAPIException
from app.db.session import get_db_session
from app.dependencies import require_permission
from app.middleware.execution_context import ExecutionContext
from app.models.result_dataset_model import ResultDatasetModel
from app.schemas.comparison import (
    ComparisonFiltersDTO,
    ComparisonRequestDTO,
    ComparisonResponseDTO,
)
from app.schemas.result_dataset import (
    ChartSpecDTO,
    DataQualitySummaryDTO,
    DatasetRowDTO,
    MeasureItemDTO,
    QuerySnapshotDTO,
    ResultDatasetDTO,
    TableColumnDTO,
    TableSpecDTO,
)
from app.services.comparison_service import ComparisonService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

perm_run = require_permission("comparisons:run")
perm_read = require_permission("comparisons:read")

ALLOWLISTED_COMPARISON_ERRORS = {
    "COMPARISON_LIMIT_EXCEEDED",
    "METRIC_NOT_SUPPORTED",
    "SEMANTIC_MEASURE_MAPPING_UNAVAILABLE",
    "CURRENCY_MISMATCH",
    "REPORTING_BASIS_MISMATCH",
    "UNIT_MISMATCH",
    "SCALE_NORMALIZATION_ERROR",
    "PERIOD_TYPE_MISMATCH",
    "EVIDENCE_INCOMPLETE",
    "EVIDENCE_SOURCE_MISMATCH",
    "EVIDENCE_FORMAT_COORDINATES_INVALID",
    "INSTITUTION_NOT_FOUND",
    "PERIOD_NOT_FOUND",
    "INCOMPLETE_COMMON_PERIOD",
    "INVALID_DECIMAL_VALUE",
    "DATA_QUALITY_INVARIANT_VIOLATED",
    "DATASET_SCHEMA_VERSION_UNSUPPORTED",
}


@router.get("/metadata/filters", response_model=ComparisonFiltersDTO)
async def get_comparison_filter_metadata(
    ctx: ExecutionContext = Depends(perm_read),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ComparisonFiltersDTO:
    """Get available institutions, periods, metrics, and supported options for comparison filtering."""
    return await ComparisonService.get_filter_metadata(db=session, organization_id=ctx.active_organization_id)


@router.post("", response_model=ComparisonResponseDTO, status_code=status.HTTP_201_CREATED)
async def execute_comparison(
    payload: ComparisonRequestDTO,
    ctx: ExecutionContext = Depends(perm_run),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ComparisonResponseDTO:
    """Execute financial comparison and return canonical ResultDataset, TableSpec, and ChartSpecs."""
    try:
        return await ComparisonService.execute_comparison(
            db=session,
            organization_id=ctx.active_organization_id,
            requested_by_user_id=ctx.authenticated_user_id,
            payload=payload,
        )
    except ValueError as e:
        err_code = str(e)
        if err_code in ALLOWLISTED_COMPARISON_ERRORS:
            status_code = status.HTTP_404_NOT_FOUND if "NOT_FOUND" in err_code else status.HTTP_400_BAD_REQUEST
            raise BaseAPIException(
                code=err_code,
                message=f"Comparison failed with error: {err_code}",
                status_code=status_code,
            )
        raise BaseAPIException(
            code="COMPARISON_INTERNAL_ERROR",
            message="Comparison failed due to an internal error.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:  # noqa: BLE001
        raise BaseAPIException(
            code="COMPARISON_INTERNAL_ERROR",
            message="Comparison failed due to an internal error.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@router.get("/{comparison_id}", response_model=ComparisonResponseDTO)
async def get_persisted_comparison(
    comparison_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ctx: ExecutionContext = Depends(perm_read),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ComparisonResponseDTO:
    """Get persisted immutable comparison dataset snapshot by ID with server-side pagination."""
    res = await session.execute(
        select(ResultDatasetModel).where(
            ResultDatasetModel.comparison_run_id == comparison_id,
            ResultDatasetModel.organization_id == ctx.active_organization_id,
        )
    )
    ds_model = res.scalar_one_or_none()
    if not ds_model:
        raise BaseAPIException(
            code="COMPARISON_NOT_FOUND",
            message="Comparison dataset not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Reader Schema Version Check
    if ds_model.schema_version not in ("1.0.0", "2.0.0", "3.0.0"):
        raise BaseAPIException(
            code="DATASET_SCHEMA_VERSION_UNSUPPORTED",
            message=f"Dataset schema version '{ds_model.schema_version}' is not supported by this engine.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    query_snap = QuerySnapshotDTO.model_validate(ds_model.query_snapshot)
    data_quality = DataQualitySummaryDTO.model_validate(ds_model.data_quality_summary)
    measures_list = [MeasureItemDTO.model_validate(m) for m in ds_model.measures_snapshot]  # type: ignore[union-attr]
    all_rows_list = [DatasetRowDTO.model_validate(r) for r in ds_model.rows_snapshot]

    total_rows = len(all_rows_list)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_rows = all_rows_list[start_idx:end_idx]

    pagination = ComparisonService._make_pagination(total_rows, page, page_size)

    result_ds = ResultDatasetDTO(
        result_dataset_id=ds_model.id,
        schema_version=ds_model.schema_version,
        generated_at=ds_model.created_at,
        query_snapshot=query_snap,
        value_source_policy=query_snap.value_source_policy,
        dimensions=ds_model.dimensions_snapshot,
        measures=measures_list,
        rows=paginated_rows,
        data_quality_summary=data_quality,
        warnings=ds_model.warnings_snapshot,
        pagination=pagination,
    )

    # Reconstruct TableSpec & ChartSpecs from paginated view
    table_cols = [
        TableColumnDTO(
            key="institution_name",
            title="Institution",
            data_type="string",
            alignment="left",
            unit_label="Text",
        ),
        TableColumnDTO(
            key="period_label",
            title="Period",
            data_type="string",
            alignment="left",
            unit_label="Text",
        ),
    ]
    for m in measures_list:
        table_cols.append(
            TableColumnDTO(
                key=m.measure_code,
                title=m.label,
                data_type="decimal" if m.unit not in ("PERCENT", "RATIO") else "percent",
                alignment="right",
                unit_label=f"{m.currency or ''} ({m.scale})" if m.unit not in ("PERCENT", "RATIO") else "%",
            )
        )

    # Rebuild table rows for paginated set
    table_spec_rows = []
    for d_row in paginated_rows:
        t_cells = {m_key: cell.model_dump(mode="python") for m_key, cell in d_row.cells.items()}
        table_spec_rows.append(
            {
                "row_id": d_row.row_id,
                "institution_name": d_row.institution_name,
                "period_label": d_row.period_label,
                "cells": t_cells,
            }
        )

    table_spec = TableSpecDTO(
        result_dataset_id=ds_model.id,
        schema_version=ds_model.schema_version,
        columns=table_cols,
        rows=table_spec_rows,  # type: ignore[arg-type]
        pagination=pagination,
    )

    chart_specs = [ChartSpecDTO.model_validate(c) for c in ds_model.chart_specs_snapshot]

    return ComparisonResponseDTO(
        comparison_id=ds_model.comparison_run_id,
        result_dataset=result_ds,
        table_spec=table_spec,
        chart_specs=chart_specs,
    )
