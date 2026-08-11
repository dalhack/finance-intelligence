import decimal
from decimal import Decimal
from typing import Any, ClassVar

from app.calculations.base import (
    BaseFormula,
    FormulaResult,
    get_working_decimal_context,
    to_working_fraction,
)


class NplRatioFormula(BaseFormula):
    formula_code = "NPL_RATIO"
    formula_version = "1.0.0"
    implementation_revision: ClassVar[str] = "1.0.0"
    algorithm_fingerprint: ClassVar[str] = "NPL_V1"
    required_input_roles: ClassVar[list[str]] = ["NUMERATOR", "DENOMINATOR"]
    expected_metric_codes: ClassVar[list[str]] = ["NPL_LOANS", "TOTAL_LOANS"]
    input_role_semantics: ClassVar[dict[str, str]] = {"NUMERATOR": "STOCK", "DENOMINATOR": "STOCK"}
    result_unit = "PERCENT"
    result_scale = "ONE"
    rounding_policy = "ROUND_HALF_UP"
    annualization_policy = "DATE_POINT"
    display_precision = 2
    tolerance_kind: ClassVar[str] = "ABSOLUTE"
    tolerance_value: ClassVar[Decimal] = Decimal("0.05")
    tolerance_unit: ClassVar[str] = "PERCENTAGE_POINTS"
    comparison_requirement: ClassVar[str] = "NONE"

    def calculate(self, inputs: dict[str, Any], metadata: dict[str, Any]) -> FormulaResult:
        npl_fact = inputs.get("NUMERATOR")
        loans_fact = inputs.get("DENOMINATOR")

        if not npl_fact or not loans_fact:
            raise ValueError("INSUFFICIENT_INPUT_FACTS")

        npl_unit = npl_fact.get("unit")
        loans_unit = loans_fact.get("unit")
        if not npl_unit or not loans_unit or npl_unit != loans_unit:
            raise ValueError("UNIT_MISMATCH")

        npl_curr = npl_fact.get("currency")
        loans_curr = loans_fact.get("currency")
        if npl_curr != loans_curr:
            raise ValueError("CURRENCY_MISMATCH")

        npl_scale = npl_fact.get("scale")
        loans_scale = loans_fact.get("scale")
        if npl_scale != loans_scale:
            raise ValueError("SCALE_NORMALIZATION_ERROR")

        npl_val = Decimal(str(npl_fact["normalized_value"]))
        loans_val = Decimal(str(loans_fact["normalized_value"]))

        ctx = get_working_decimal_context()
        with decimal.localcontext(ctx):
            npl_frac = to_working_fraction(npl_val, npl_unit)
            loans_frac = to_working_fraction(loans_val, loans_unit)

            if loans_frac == Decimal("0.0"):
                raise ValueError("DIVISION_BY_ZERO")

            ratio = npl_frac / loans_frac
            pct_unrounded = ratio * Decimal("100.0")

            pattern = Decimal(10) ** (-self.display_precision)
            pct_display = pct_unrounded.quantize(pattern, rounding=decimal.ROUND_HALF_UP)

            return FormulaResult(
                result_value_unrounded=pct_unrounded,
                result_value_display=pct_display,
                result_unit="PERCENT",
                result_scale="ONE",
                value_representation="PERCENT_DISPLAY",
                rounding_policy=self.rounding_policy,
                display_precision=self.display_precision,
            )
