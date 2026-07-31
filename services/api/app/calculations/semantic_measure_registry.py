from dataclasses import dataclass
from typing import ClassVar, Literal


@dataclass(frozen=True)
class SemanticMeasureDefinition:
    semantic_measure_code: str
    display_name: str
    reported_metric_code: str | None
    derived_formula_code: str | None
    result_unit: Literal["CURRENCY", "PERCENT", "RATIO"]
    currency_semantics: Literal["REQUIRED", "PROHIBITED"]
    scale_semantics: Literal["ALLOWED", "NONE"]
    registry_version: str = "1.0.0"


class SemanticMeasureRegistry:
    _DEFINITIONS: ClassVar[dict[str, SemanticMeasureDefinition]] = {
        "TOTAL_ASSETS": SemanticMeasureDefinition(
            semantic_measure_code="TOTAL_ASSETS",
            display_name="Total Assets",
            reported_metric_code="TOTAL_ASSETS",
            derived_formula_code=None,
            result_unit="CURRENCY",
            currency_semantics="REQUIRED",
            scale_semantics="ALLOWED",
        ),
        "TOTAL_DEPOSITS": SemanticMeasureDefinition(
            semantic_measure_code="TOTAL_DEPOSITS",
            display_name="Total Deposits",
            reported_metric_code="TOTAL_DEPOSITS",
            derived_formula_code=None,
            result_unit="CURRENCY",
            currency_semantics="REQUIRED",
            scale_semantics="ALLOWED",
        ),
        "TOTAL_LOANS": SemanticMeasureDefinition(
            semantic_measure_code="TOTAL_LOANS",
            display_name="Total Loans",
            reported_metric_code="TOTAL_LOANS",
            derived_formula_code=None,
            result_unit="CURRENCY",
            currency_semantics="REQUIRED",
            scale_semantics="ALLOWED",
        ),
        "NON_PERFORMING_LOANS": SemanticMeasureDefinition(
            semantic_measure_code="NON_PERFORMING_LOANS",
            display_name="Non-Performing Loans",
            reported_metric_code="NON_PERFORMING_LOANS",
            derived_formula_code=None,
            result_unit="CURRENCY",
            currency_semantics="REQUIRED",
            scale_semantics="ALLOWED",
        ),
        "NET_INCOME": SemanticMeasureDefinition(
            semantic_measure_code="NET_INCOME",
            display_name="Net Income",
            reported_metric_code="NET_INCOME",
            derived_formula_code=None,
            result_unit="CURRENCY",
            currency_semantics="REQUIRED",
            scale_semantics="ALLOWED",
        ),
        "TOTAL_EQUITY": SemanticMeasureDefinition(
            semantic_measure_code="TOTAL_EQUITY",
            display_name="Total Equity",
            reported_metric_code="TOTAL_EQUITY",
            derived_formula_code=None,
            result_unit="CURRENCY",
            currency_semantics="REQUIRED",
            scale_semantics="ALLOWED",
        ),
        "LOAN_TO_DEPOSIT_RATIO": SemanticMeasureDefinition(
            semantic_measure_code="LOAN_TO_DEPOSIT_RATIO",
            display_name="Loan to Deposit Ratio",
            reported_metric_code="LOAN_TO_DEPOSIT_RATIO",
            derived_formula_code="LOAN_TO_DEPOSIT_RATIO",
            result_unit="PERCENT",
            currency_semantics="PROHIBITED",
            scale_semantics="NONE",
        ),
        "NPL_RATIO": SemanticMeasureDefinition(
            semantic_measure_code="NPL_RATIO",
            display_name="Non-Performing Loans Ratio",
            reported_metric_code="NPL_RATIO",
            derived_formula_code="NPL_RATIO",
            result_unit="PERCENT",
            currency_semantics="PROHIBITED",
            scale_semantics="NONE",
        ),
        "GROWTH_RATE": SemanticMeasureDefinition(
            semantic_measure_code="GROWTH_RATE",
            display_name="Growth Rate",
            reported_metric_code=None,
            derived_formula_code="GROWTH_RATE",
            result_unit="PERCENT",
            currency_semantics="PROHIBITED",
            scale_semantics="NONE",
        ),
        "RETURN_ON_ASSETS": SemanticMeasureDefinition(
            semantic_measure_code="RETURN_ON_ASSETS",
            display_name="Return on Assets",
            reported_metric_code="RETURN_ON_ASSETS",
            derived_formula_code="RETURN_ON_ASSETS",
            result_unit="PERCENT",
            currency_semantics="PROHIBITED",
            scale_semantics="NONE",
        ),
        "RETURN_ON_EQUITY": SemanticMeasureDefinition(
            semantic_measure_code="RETURN_ON_EQUITY",
            display_name="Return on Equity",
            reported_metric_code="RETURN_ON_EQUITY",
            derived_formula_code="RETURN_ON_EQUITY",
            result_unit="PERCENT",
            currency_semantics="PROHIBITED",
            scale_semantics="NONE",
        ),
    }

    @classmethod
    def get(cls, code: str) -> SemanticMeasureDefinition:
        """Get semantic measure definition or raise SEMANTIC_MEASURE_MAPPING_UNAVAILABLE."""
        defn = cls._DEFINITIONS.get(code)
        if not defn:
            raise ValueError("SEMANTIC_MEASURE_MAPPING_UNAVAILABLE")
        return defn

    @classmethod
    def list_all(cls) -> list[SemanticMeasureDefinition]:
        return list(cls._DEFINITIONS.values())
