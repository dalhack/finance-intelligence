from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.api.app.schemas.comparison import ComparisonRequestDTO, SemanticMeasureSelectorDTO
from services.api.app.schemas.result_dataset import (
    ChartSeriesDTO,
    ChartSpecDTO,
    DataQualitySummaryDTO,
)
from services.api.app.services.comparison_service import ComparisonService


def test_reporting_basis_solo_and_consolidated():
    """Verify SOLO and CONSOLIDATED reporting basis are accepted, others rejected."""
    inst_id = uuid4()
    period_id = uuid4()

    # SOLO
    req_solo = ComparisonRequestDTO(
        institution_ids=[inst_id],
        semantic_measures=[SemanticMeasureSelectorDTO(semantic_measure_code="TOTAL_ASSETS")],
        reporting_period_ids=[period_id],
        reporting_basis="SOLO",
    )
    assert req_solo.reporting_basis == "SOLO"

    # CONSOLIDATED
    req_cons = ComparisonRequestDTO(
        institution_ids=[inst_id],
        semantic_measures=[SemanticMeasureSelectorDTO(semantic_measure_code="TOTAL_ASSETS")],
        reporting_period_ids=[period_id],
        reporting_basis="CONSOLIDATED",
    )
    assert req_cons.reporting_basis == "CONSOLIDATED"

    # Reject ACCURAL, ACCRUAL, CASH, UNKNOWN
    for invalid_b in ("ACCURAL", "ACCRUAL", "CASH", "UNKNOWN"):
        with pytest.raises(ValidationError):
            ComparisonRequestDTO(
                institution_ids=[inst_id],
                semantic_measures=[SemanticMeasureSelectorDTO(semantic_measure_code="TOTAL_ASSETS")],
                reporting_period_ids=[period_id],
                reporting_basis=invalid_b,
            )


def test_decimal_sorting_without_float():
    """Verify Decimal sorting maintains exact precision without float conversion."""
    val1 = Decimal("10000000000000000.0001")
    val2 = Decimal("10000000000000000.0002")

    # Safe decimal helper check
    d1 = ComparisonService._safe_decimal(str(val1))
    d2 = ComparisonService._safe_decimal(str(val2))
    assert d1 < d2
    assert type(d1) is Decimal

    # Invalid decimal rejection
    for bad_val in ("NaN", "Infinity", "-Infinity", "abc"):
        with pytest.raises(ValueError, match="INVALID_DECIMAL_VALUE"):
            ComparisonService._safe_decimal(bad_val)


def test_completeness_and_data_quality_summary_invariant():
    """Verify completeness percentage formula and data quality summary invariant validation."""
    # 3 expected, 2 populated, 1 missing -> expected (3) == 2 + 1 + 0 + 0
    expected = 3
    populated = 2
    comp_pct = (Decimal(str(populated)) / Decimal(str(expected))) * Decimal(100)
    comp_str = str(comp_pct.quantize(Decimal("0.01")))
    assert comp_str == "66.67"

    dq = DataQualitySummaryDTO(
        expected_cells=3,
        populated_cells=2,
        missing_source_cells=1,
        excluded_ineligible_cells=0,
        excluded_mismatch_cells=0,
        warning_cells=0,
        source_reported_count=2,
        system_derived_count=0,
        reconciliation_warning_count=0,
        completeness_percentage=comp_str,
    )
    assert dq.completeness_percentage == "66.67"

    # Invariant failure: expected=3, but sum=4
    with pytest.raises(ValidationError, match="DATA_QUALITY_INVARIANT_VIOLATED"):
        DataQualitySummaryDTO(
            expected_cells=3,
            populated_cells=2,
            missing_source_cells=2,
            excluded_ineligible_cells=0,
            excluded_mismatch_cells=0,
            warning_cells=0,
            source_reported_count=2,
            system_derived_count=0,
            reconciliation_warning_count=0,
            completeness_percentage=comp_str,
        )


def test_real_pagination_dto():
    """Verify PaginationDTO calculation logic."""
    pag = ComparisonService._make_pagination(total_rows=45, page=2, page_size=20)
    assert pag.total_rows == 45
    assert pag.total_pages == 3
    assert pag.has_next is True
    assert pag.has_previous is True

    pag_last = ComparisonService._make_pagination(total_rows=45, page=3, page_size=20)
    assert pag_last.has_next is False
    assert pag_last.has_previous is True


def test_mixed_unit_chart_spec_separation():
    """Verify ChartSpecDTO carries unit and currency per series and separates monetary from percentage."""
    cs_monetary = ChartSpecDTO(
        result_dataset_id=uuid4(),
        chart_type="vertical_bar",
        title="Monetary Comparison",
        x_axis_label="Institution / Period",
        y_axis_label="MILLION",
        unit="CURRENCY",
        currency="TRY",
        series=[
            ChartSeriesDTO(
                series_name="Total Assets",
                semantic_measure_code="TOTAL_ASSETS",
                measure_code="TOTAL_ASSETS",
                unit="CURRENCY",
                currency="TRY",
                data_points=[],
            )
        ],
    )
    assert cs_monetary.unit == "CURRENCY"
    assert cs_monetary.currency == "TRY"

    cs_percent = ChartSpecDTO(
        result_dataset_id=uuid4(),
        chart_type="line",
        title="Ratio Comparison",
        x_axis_label="Institution / Period",
        y_axis_label="PERCENT",
        unit="PERCENT",
        currency=None,
        series=[
            ChartSeriesDTO(
                series_name="Return on Assets",
                semantic_measure_code="RETURN_ON_ASSETS",
                measure_code="RETURN_ON_ASSETS",
                unit="PERCENT",
                currency=None,
                data_points=[],
            )
        ],
    )
    assert cs_percent.unit == "PERCENT"
    assert cs_percent.currency is None
