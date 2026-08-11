import decimal
from decimal import Decimal
from typing import Any, ClassVar

from app.calculations.base import (
    BaseFormula,
    FormulaResult,
    get_working_decimal_context,
    to_working_fraction,
)


class GrowthRateFormula(BaseFormula):
    formula_code = "GROWTH_RATE"
    formula_version = "1.0.0"
    implementation_revision: ClassVar[str] = "1.0.0"
    algorithm_fingerprint: ClassVar[str] = "GROWTH_V1"
    required_input_roles: ClassVar[list[str]] = ["CURRENT_VALUE", "COMPARISON_VALUE"]
    expected_metric_codes: ClassVar[list[str]] = ["METRIC_CURRENT", "METRIC_COMPARISON"]
    input_role_semantics: ClassVar[dict[str, str]] = {"CURRENT_VALUE": "STOCK", "COMPARISON_VALUE": "STOCK"}
    result_unit = "PERCENT"
    result_scale = "ONE"
    rounding_policy = "ROUND_HALF_UP"
    annualization_policy = "DISCRETE_PERIOD"
    display_precision = 2
    tolerance_kind: ClassVar[str] = "ABSOLUTE"
    tolerance_value: ClassVar[Decimal] = Decimal("0.01")
    tolerance_unit: ClassVar[str] = "PERCENTAGE_POINTS"
    comparison_requirement: ClassVar[str] = "REQUIRED_COMPARISON"

    def calculate(self, inputs: dict[str, Any], metadata: dict[str, Any]) -> FormulaResult:
        cur_fact = inputs.get("CURRENT_VALUE")
        comp_fact = inputs.get("COMPARISON_VALUE")

        if not cur_fact or not comp_fact:
            raise ValueError("INSUFFICIENT_INPUT_FACTS")

        cur_unit = cur_fact.get("unit")
        comp_unit = comp_fact.get("unit")
        if not cur_unit or not comp_unit or cur_unit != comp_unit:
            raise ValueError("UNIT_MISMATCH")

        cur_curr = cur_fact.get("currency")
        comp_curr = comp_fact.get("currency")
        if cur_curr != comp_curr:
            raise ValueError("CURRENCY_MISMATCH")

        cur_scale = cur_fact.get("scale")
        comp_scale = comp_fact.get("scale")
        if cur_scale != comp_scale:
            raise ValueError("SCALE_NORMALIZATION_ERROR")

        cur_val = Decimal(str(cur_fact["normalized_value"]))
        comp_val = Decimal(str(comp_fact["normalized_value"]))

        ctx = get_working_decimal_context()
        with decimal.localcontext(ctx):
            cur_frac = to_working_fraction(cur_val, cur_unit)
            comp_frac = to_working_fraction(comp_val, comp_unit)

            if comp_frac == Decimal("0.0"):
                raise ValueError("DIVISION_BY_ZERO")

            growth_rate = (cur_frac / comp_frac) - Decimal("1.0")
            pct_unrounded = growth_rate * Decimal("100.0")

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
