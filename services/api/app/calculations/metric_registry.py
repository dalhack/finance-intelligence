from typing import ClassVar, Literal


class MetricRegistry:
    REPORTED_METRICS: ClassVar[dict[str, str]] = {
        "TOTAL_ASSETS": "Total Assets",
        "TOTAL_DEPOSITS": "Total Deposits",
        "TOTAL_LOANS": "Total Loans",
        "NON_PERFORMING_LOANS": "Non-Performing Loans",
        "NET_INCOME": "Net Income",
        "TOTAL_EQUITY": "Total Equity",
    }

    DERIVED_FORMULAS: ClassVar[dict[str, str]] = {
        "LOAN_TO_DEPOSIT_RATIO": "Loan to Deposit Ratio",
        "NPL_RATIO": "Non-Performing Loans Ratio",
        "GROWTH_RATE": "Growth Rate",
        "RETURN_ON_ASSETS": "Return on Assets",
        "RETURN_ON_EQUITY": "Return on Equity",
    }

    @classmethod
    def classify_code(cls, code: str) -> Literal["REPORTED", "DERIVED"]:
        if code in cls.REPORTED_METRICS:
            return "REPORTED"
        if code in cls.DERIVED_FORMULAS:
            return "DERIVED"
        raise ValueError("METRIC_NOT_SUPPORTED")

    @classmethod
    def get_label(cls, code: str) -> str:
        if code in cls.REPORTED_METRICS:
            return cls.REPORTED_METRICS[code]
        if code in cls.DERIVED_FORMULAS:
            return cls.DERIVED_FORMULAS[code]
        raise ValueError("METRIC_NOT_SUPPORTED")
