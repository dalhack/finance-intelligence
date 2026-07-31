import decimal
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, ClassVar

WORKING_PRECISION = 38
WORKING_SCALE = 10


def get_working_decimal_context() -> decimal.Context:
    """Return explicit local Working Precision Decimal Context (prec=38)."""
    return decimal.Context(prec=WORKING_PRECISION, rounding=decimal.ROUND_HALF_UP)


def to_working_fraction(value: Decimal, unit: str) -> Decimal:
    """Centralized percentage contract adapter.

    Converts percentage display value (e.g. 18.42) into decimal fraction (0.1842)
    iff unit == 'PERCENT'.
    Raises ValueError if unit is missing or unsupported.
    """
    if not unit:
        raise ValueError("UNIT_MISMATCH")
    ctx = get_working_decimal_context()
    with decimal.localcontext(ctx):
        dec_val = Decimal(str(value))
        if unit == "PERCENT":
            return dec_val / Decimal("100.0")
        elif unit in ("CURRENCY", "COUNT", "RATIO", "ONE"):
            return dec_val
        else:
            raise ValueError("UNIT_MISMATCH")


@dataclass(frozen=True)
class FormulaResult:
    result_value_unrounded: Decimal
    result_value_display: Decimal
    result_unit: str
    result_scale: str
    value_representation: str  # PERCENT_DISPLAY, DECIMAL_FRACTION, RATIO
    rounding_policy: str = "ROUND_HALF_UP"
    display_precision: int = 2

    def to_quantized_display(self) -> Decimal:
        """Quantize final unrounded result to display precision using ROUND_HALF_UP in local context."""
        ctx = get_working_decimal_context()
        with decimal.localcontext(ctx):
            pattern = Decimal(10) ** (-self.display_precision)
            return self.result_value_unrounded.quantize(pattern, rounding=decimal.ROUND_HALF_UP)


class BaseFormula(ABC):
    formula_code: str
    formula_version: str
    implementation_revision: ClassVar[str] = "1.0.0"
    algorithm_fingerprint: ClassVar[str] = "ALG_V1"
    required_input_roles: ClassVar[list[str]]
    expected_metric_codes: ClassVar[list[str]]
    input_role_semantics: ClassVar[dict[str, str]] = {}
    result_unit: str
    result_scale: str
    rounding_policy: str
    annualization_policy: str
    display_precision: int
    tolerance_kind: ClassVar[str] = "ABSOLUTE"
    tolerance_value: ClassVar[Decimal] = Decimal("0.05")
    tolerance_unit: ClassVar[str] = "PERCENTAGE_POINTS"
    tolerance_policy_version: ClassVar[str] = "1.0.0"
    comparison_requirement: ClassVar[str] = "NONE"  # NONE, REQUIRED_COMPARISON, REQUIRED_BEGINNING_BALANCE

    @abstractmethod
    def calculate(self, inputs: dict[str, Any], metadata: dict[str, Any]) -> FormulaResult:
        pass
