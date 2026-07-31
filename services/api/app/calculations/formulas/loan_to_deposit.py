import decimal
from decimal import Decimal
from typing import Any, ClassVar

from services.api.app.calculations.base import (
    BaseFormula,
    FormulaResult,
    get_working_decimal_context,
    to_working_fraction,
)


class LoanToDepositRatioFormula(BaseFormula):
    formula_code = "LOAN_TO_DEPOSIT_RATIO"
    formula_version = "1.0.0"
    implementation_revision: ClassVar[str] = "1.0.0"
    algorithm_fingerprint: ClassVar[str] = "LDR_V1"
    required_input_roles: ClassVar[list[str]] = ["NUMERATOR", "DENOMINATOR"]
    expected_metric_codes: ClassVar[list[str]] = ["TOTAL_LOANS", "TOTAL_DEPOSITS"]
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
        loans_fact = inputs.get("NUMERATOR")
        deposits_fact = inputs.get("DENOMINATOR")

        if not loans_fact or not deposits_fact:
            raise ValueError("INSUFFICIENT_INPUT_FACTS")

        loans_unit = loans_fact.get("unit")
        deposits_unit = deposits_fact.get("unit")
        if not loans_unit or not deposits_unit or loans_unit != deposits_unit:
            raise ValueError("UNIT_MISMATCH")

        loans_curr = loans_fact.get("currency")
        deposits_curr = deposits_fact.get("currency")
        if loans_curr != deposits_curr:
            raise ValueError("CURRENCY_MISMATCH")

        loans_scale = loans_fact.get("scale")
        deposits_scale = deposits_fact.get("scale")
        if loans_scale != deposits_scale:
            raise ValueError("SCALE_NORMALIZATION_ERROR")

        loans_val = Decimal(str(loans_fact["normalized_value"]))
        deposits_val = Decimal(str(deposits_fact["normalized_value"]))

        ctx = get_working_decimal_context()
        with decimal.localcontext(ctx):
            loans_frac = to_working_fraction(loans_val, loans_unit)
            deposits_frac = to_working_fraction(deposits_val, deposits_unit)

            if deposits_frac == Decimal("0.0"):
                raise ValueError("DIVISION_BY_ZERO")

            ratio = loans_frac / deposits_frac
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
