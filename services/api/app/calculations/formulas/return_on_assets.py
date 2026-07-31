import decimal
from decimal import Decimal
from typing import Any, ClassVar

from services.api.app.calculations.base import (
    BaseFormula,
    FormulaResult,
    get_working_decimal_context,
    to_working_fraction,
)


class ReturnOnAssetsFormula(BaseFormula):
    formula_code = "RETURN_ON_ASSETS"
    formula_version = "1.0.0"
    implementation_revision: ClassVar[str] = "1.0.0"
    algorithm_fingerprint: ClassVar[str] = "ROA_V1"
    required_input_roles: ClassVar[list[str]] = ["PERIOD_INCOME", "BEGINNING_BALANCE", "ENDING_BALANCE"]
    expected_metric_codes: ClassVar[list[str]] = ["NET_INCOME", "TOTAL_ASSETS"]
    input_role_semantics: ClassVar[dict[str, str]] = {
        "PERIOD_INCOME": "FLOW",
        "BEGINNING_BALANCE": "STOCK",
        "ENDING_BALANCE": "STOCK",
    }
    result_unit = "PERCENT"
    result_scale = "ONE"
    rounding_policy = "ROUND_HALF_UP"
    annualization_policy = "YEAR_TO_DATE"
    display_precision = 2
    tolerance_kind: ClassVar[str] = "ABSOLUTE"
    tolerance_value: ClassVar[Decimal] = Decimal("0.05")
    tolerance_unit: ClassVar[str] = "PERCENTAGE_POINTS"
    comparison_requirement: ClassVar[str] = "REQUIRED_BEGINNING_BALANCE"

    def calculate(self, inputs: dict[str, Any], metadata: dict[str, Any]) -> FormulaResult:
        net_income_fact = inputs.get("PERIOD_INCOME")
        beg_assets_fact = inputs.get("BEGINNING_BALANCE")
        end_assets_fact = inputs.get("ENDING_BALANCE")

        if not net_income_fact or not beg_assets_fact or not end_assets_fact:
            raise ValueError("INSUFFICIENT_INPUT_FACTS")

        # ROA Policy: Beginning balance and ending balance must be distinct
        beg_fact_id = beg_assets_fact.get("id")
        end_fact_id = end_assets_fact.get("id")
        if beg_fact_id and end_fact_id and beg_fact_id == end_fact_id:
            raise ValueError("DUPLICATE_BALANCE_INPUT")

        inc_unit = net_income_fact.get("unit")
        beg_unit = beg_assets_fact.get("unit")
        end_unit = end_assets_fact.get("unit")
        if not inc_unit or not beg_unit or not end_unit or beg_unit != end_unit:
            raise ValueError("UNIT_MISMATCH")

        inc_curr = net_income_fact.get("currency")
        beg_curr = beg_assets_fact.get("currency")
        end_curr = end_assets_fact.get("currency")
        if beg_curr != end_curr or inc_curr != beg_curr:
            raise ValueError("CURRENCY_MISMATCH")

        income_val = Decimal(str(net_income_fact["normalized_value"]))
        beg_val = Decimal(str(beg_assets_fact["normalized_value"]))
        end_val = Decimal(str(end_assets_fact["normalized_value"]))

        annualization_factor = Decimal(str(metadata.get("annualization_factor", "1.0")))

        ctx = get_working_decimal_context()
        with decimal.localcontext(ctx):
            inc_frac = to_working_fraction(income_val, inc_unit)
            beg_frac = to_working_fraction(beg_val, beg_unit)
            end_frac = to_working_fraction(end_val, end_unit)

            avg_assets = (beg_frac + end_frac) / Decimal("2.0")
            if avg_assets == Decimal("0.0"):
                raise ValueError("DIVISION_BY_ZERO")

            roa_fraction = (inc_frac / avg_assets) * annualization_factor
            roa_pct_unrounded = roa_fraction * Decimal("100.0")

            pattern = Decimal(10) ** (-self.display_precision)
            roa_pct_display = roa_pct_unrounded.quantize(pattern, rounding=decimal.ROUND_HALF_UP)

            return FormulaResult(
                result_value_unrounded=roa_pct_unrounded,
                result_value_display=roa_pct_display,
                result_unit="PERCENT",
                result_scale="ONE",
                value_representation="PERCENT_DISPLAY",
                rounding_policy=self.rounding_policy,
                display_precision=self.display_precision,
            )
