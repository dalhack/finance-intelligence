from datetime import date
from decimal import Decimal

import pytest

from services.api.app.services.calculation_service import CalculationService


@pytest.mark.unit
def test_act_isda_single_normal_year():
    """Verify ACT/ACT_ISDA annualization for a period within a normal 365-day calendar year."""
    start_date = date(2023, 1, 1)
    end_date = date(2023, 6, 30)
    factor = CalculationService.compute_act_isda_annualization_factor(
        start_date=start_date,
        end_date=end_date,
        presentation="FULL_YEAR",
        input_semantics={"NUMERATOR": "STOCK"},
    )
    assert factor == Decimal("1.0")

    # Periodic presentation
    factor_periodic = CalculationService.compute_act_isda_annualization_factor(
        start_date=start_date,
        end_date=end_date,
        presentation="QUARTERLY",
        input_semantics={"PERIOD_INCOME": "FLOW"},
    )
    days_in_period = (end_date - start_date).days + 1  # 181 days
    year_fraction = Decimal(days_in_period) / Decimal(365)
    expected_factor = Decimal("1.0") / year_fraction
    assert factor_periodic == expected_factor


@pytest.mark.unit
def test_act_isda_single_leap_year():
    """Verify ACT/ACT_ISDA annualization for a period within a 366-day leap year (2024)."""
    start_date = date(2024, 1, 1)
    end_date = date(2024, 12, 31)
    factor = CalculationService.compute_act_isda_annualization_factor(
        start_date=start_date,
        end_date=end_date,
        presentation="FULL_YEAR",
        input_semantics={"NUMERATOR": "STOCK"},
    )
    assert factor == Decimal("1.0")


@pytest.mark.unit
def test_act_isda_multi_year_spanning():
    """Verify ACT/ACT_ISDA annualization for a period spanning calendar year boundary."""
    start_date = date(2023, 7, 1)
    end_date = date(2024, 6, 30)
    factor = CalculationService.compute_act_isda_annualization_factor(
        start_date=start_date,
        end_date=end_date,
        presentation="TRAILING_TWELVE_MONTHS",
        input_semantics={"PERIOD_INCOME": "FLOW"},
    )
    # TTM presentation returns 1.0
    assert factor == Decimal("1.0")

    factor_periodic = CalculationService.compute_act_isda_annualization_factor(
        start_date=start_date,
        end_date=end_date,
        presentation="SEMI_ANNUAL",
        input_semantics={"PERIOD_INCOME": "FLOW"},
    )
    d1 = (date(2023, 12, 31) - start_date).days + 1  # 184 days in 2023 (365 days)
    d2 = (end_date - date(2024, 1, 1)).days + 1  # 182 days in 2024 (366 days)
    year_fraction = (Decimal(d1) / Decimal(365)) + (Decimal(d2) / Decimal(366))
    expected = Decimal("1.0") / year_fraction
    assert factor_periodic == expected


@pytest.mark.unit
def test_act_isda_date_point_rejection():
    """Verify DATE_POINT presentation allows STOCK metrics (factor 1.0) and rejects FLOW metrics."""
    start_date = date(2024, 3, 31)
    end_date = date(2024, 3, 31)

    # STOCK metrics -> factor 1.0
    factor_stock = CalculationService.compute_act_isda_annualization_factor(
        start_date=start_date,
        end_date=end_date,
        presentation="DATE_POINT",
        input_semantics={"NUMERATOR": "STOCK", "DENOMINATOR": "STOCK"},
    )
    assert factor_stock == Decimal("1.0")

    # FLOW metric -> raises ANNUALIZATION_POLICY_UNRESOLVED
    with pytest.raises(ValueError, match="ANNUALIZATION_POLICY_UNRESOLVED"):
        CalculationService.compute_act_isda_annualization_factor(
            start_date=start_date,
            end_date=end_date,
            presentation="DATE_POINT",
            input_semantics={"PERIOD_INCOME": "FLOW", "BEGINNING_BALANCE": "STOCK"},
        )
