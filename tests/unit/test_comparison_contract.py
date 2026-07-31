from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.api.app.calculations.semantic_measure_registry import SemanticMeasureRegistry
from services.api.app.schemas.comparison import ComparisonRequestDTO
from services.api.app.schemas.result_dataset import (
    ChartSpecDTO,
    DatasetRowCellDTO,
    PaginationDTO,
    TableColumnDTO,
    TableSpecDTO,
)


def test_comparison_request_extra_fields_rejection():
    """Verify ComparisonRequestDTO forbids extra fields like tenant_id, organization_id, or user_id."""
    inst_id = uuid4()
    period_id = uuid4()

    valid_payload = {
        "institution_ids": [str(inst_id)],
        "semantic_measures": [{"semantic_measure_code": "TOTAL_ASSETS", "preferred_origin": "AUTO"}],
        "reporting_period_ids": [str(period_id)],
        "reporting_basis": "SOLO",
    }
    req = ComparisonRequestDTO.model_validate(valid_payload)
    assert req.semantic_measures[0].semantic_measure_code == "TOTAL_ASSETS"
    assert req.reporting_basis == "SOLO"

    # Reject ACCURAL/CASH/UNKNOWN as reporting_basis
    for invalid_basis in ("ACCURAL", "ACCRUAL", "CASH", "UNKNOWN"):
        with pytest.raises(ValidationError):
            ComparisonRequestDTO.model_validate({**valid_payload, "reporting_basis": invalid_basis})

    # Reject organization_id in request payload
    with pytest.raises(ValidationError):
        ComparisonRequestDTO.model_validate({**valid_payload, "organization_id": str(uuid4())})

    # Reject tenant_id in request payload
    with pytest.raises(ValidationError):
        ComparisonRequestDTO.model_validate({**valid_payload, "tenant_id": str(uuid4())})

    # Reject roles in request payload
    with pytest.raises(ValidationError):
        ComparisonRequestDTO.model_validate({**valid_payload, "roles": ["ADMIN"]})


def test_semantic_measure_registry_lookup():
    """Verify SemanticMeasureRegistry correctly maps canonical codes and metadata."""
    defn_assets = SemanticMeasureRegistry.get("TOTAL_ASSETS")
    assert defn_assets.reported_metric_code == "TOTAL_ASSETS"
    assert defn_assets.result_unit == "CURRENCY"
    assert defn_assets.currency_semantics == "REQUIRED"

    defn_roa = SemanticMeasureRegistry.get("RETURN_ON_ASSETS")
    assert defn_roa.reported_metric_code == "RETURN_ON_ASSETS"
    assert defn_roa.derived_formula_code == "RETURN_ON_ASSETS"
    assert defn_roa.result_unit == "PERCENT"
    assert defn_roa.currency_semantics == "PROHIBITED"

    with pytest.raises(ValueError, match="SEMANTIC_MEASURE_MAPPING_UNAVAILABLE"):
        SemanticMeasureRegistry.get("UNKNOWN_MEASURE_999")


def test_result_dataset_dto_lossless_decimal_serialization():
    """Verify financial values in ResultDatasetDTO are carried as lossless Decimal strings without float loss."""
    val_str = "123456789012345678.9012"
    cell = DatasetRowCellDTO(
        measure_code="TOTAL_ASSETS",
        semantic_measure_code="TOTAL_ASSETS",
        canonical_value=val_str,
        display_value="123,456.79",
        value_origin="SOURCE_REPORTED",
    )
    assert cell.canonical_value == val_str
    # Verify exact Decimal conversion
    assert Decimal(cell.canonical_value) == Decimal("123456789012345678.9012")


def test_table_spec_and_chart_spec_consistency():
    """Verify TableSpec and ChartSpec bind to the same result_dataset_id and maintain value equality."""
    dataset_id = uuid4()
    pag = PaginationDTO(page=1, page_size=20, total_rows=0, total_pages=1, has_next=False, has_previous=False)
    t_spec = TableSpecDTO(
        result_dataset_id=dataset_id,
        schema_version="3.0.0",
        columns=[TableColumnDTO(key="inst", title="Institution", data_type="string", unit_label="Text")],
        rows=[],
        pagination=pag,
    )
    c_spec = ChartSpecDTO(
        result_dataset_id=dataset_id,
        chart_type="vertical_bar",
        title="Comparison Chart",
        x_axis_label="Institution",
        y_axis_label="Million",
        unit="TRY",
        series=[],
    )

    assert t_spec.result_dataset_id == dataset_id
    assert c_spec.result_dataset_id == dataset_id
    assert t_spec.schema_version == "3.0.0"
