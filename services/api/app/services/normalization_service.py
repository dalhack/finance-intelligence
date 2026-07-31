import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import NamedTuple

SCALE_FACTORS: dict[str, Decimal] = {
    "ONE": Decimal(1),
    "THOUSAND": Decimal(1000),
    "MILLION": Decimal(1000000),
    "BILLION": Decimal(1000000000),
}

VALID_CURRENCIES: set[str] = {"TRY", "USD", "EUR", "GBP", "CHF", "JPY"}
VALID_UNITS: set[str] = {"CURRENCY", "PERCENT", "RATIO", "COUNT"}
VALID_SCALES: set[str] = {"ONE", "THOUSAND", "MILLION", "BILLION"}
VALID_BASES: set[str] = {"SOLO", "CONSOLIDATED", "UNKNOWN"}


class NumberParseResult(NamedTuple):
    value: Decimal | None
    is_percentage: bool
    warning_codes: list[str]


class NormalizationService:
    @staticmethod
    def parse_financial_decimal(raw_val: str, locale_hint: str | None = None) -> NumberParseResult:
        """Parse financial numbers supporting TR/EN locales, negative parentheses, and percentages."""
        if not raw_val or not raw_val.strip():
            return NumberParseResult(value=None, is_percentage=False, warning_codes=["EMPTY_VALUE"])

        cleaned = raw_val.strip()
        warnings: list[str] = []

        # Check for non-numeric null indicators
        if cleaned in {"—", "-", "N/A", "n/a", "null", "NULL", "None", ""}:
            return NumberParseResult(value=None, is_percentage=False, warning_codes=["MISSING_VALUE"])

        # Check for forbidden exponent notation or special float values
        lower_cleaned = cleaned.lower()
        if re.search(r"\d+e[+-]?\d+", lower_cleaned) or any(k in lower_cleaned for k in ("nan", "inf")):
            return NumberParseResult(
                value=None, is_percentage=False, warning_codes=["FORBIDDEN_EXPONENT_OR_SPECIAL_FLOAT"]
            )

        # Check for percentage symbol
        is_percentage = "%" in cleaned or "yüzde" in cleaned.lower()
        cleaned = re.sub(r"[%\s]", "", cleaned)
        cleaned = re.sub(r"(?i)yüzde", "", cleaned)

        # Check for negative parenthesis (e.g. (1.250) -> -1.250)
        is_negative = False
        if cleaned.startswith("(") and cleaned.endswith(")"):
            is_negative = True
            cleaned = cleaned[1:-1].strip()
        elif cleaned.startswith("-"):
            is_negative = True
            cleaned = cleaned[1:].strip()

        # Separator analysis
        has_dot = "." in cleaned
        has_comma = "," in cleaned

        if has_dot and has_comma:
            # Dual separator: last separator is decimal separator
            dot_idx = cleaned.rfind(".")
            comma_idx = cleaned.rfind(",")
            if dot_idx > comma_idx:
                # EN format: 1,234,567.89 -> remove comma
                norm_str = cleaned.replace(",", "")
            else:
                # TR format: 1.234.567,89 -> remove dot, replace comma with dot
                norm_str = cleaned.replace(".", "").replace(",", ".")
        elif has_comma and not has_dot:
            # Single comma
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) in (1, 2):
                # TR decimal comma: 1234,89 -> 1234.89
                norm_str = cleaned.replace(",", ".")
            elif len(parts) > 2:
                # Thousands comma: 1,234,567 -> 1234567
                norm_str = cleaned.replace(",", "")
            else:
                # Ambiguous single comma if length of decimals is 3 (e.g. 1,250)
                if locale_hint == "tr_TR" or locale_hint == "TR":
                    norm_str = cleaned.replace(",", "")
                else:
                    norm_str = cleaned.replace(",", "")
                    warnings.append("AMBIGUOUS_NUMBER_FORMAT")
        elif has_dot and not has_comma:
            # Single dot
            parts = cleaned.split(".")
            if len(parts) == 2 and len(parts[1]) in (1, 2):
                # EN decimal dot: 1234.89
                norm_str = cleaned
            elif len(parts) > 2:
                # TR thousands dot: 1.234.567 -> 1234567
                norm_str = cleaned.replace(".", "")
            else:
                # Ambiguous single dot if 3 decimal digits (e.g. 1.250)
                if locale_hint == "en_US" or locale_hint == "EN":
                    norm_str = cleaned
                else:
                    norm_str = cleaned.replace(".", "")
                    warnings.append("AMBIGUOUS_NUMBER_FORMAT")
        else:
            norm_str = cleaned

        try:
            val = Decimal(norm_str)
            if is_negative:
                val = -val
            return NumberParseResult(value=val, is_percentage=is_percentage, warning_codes=warnings)
        except (InvalidOperation, TypeError):
            return NumberParseResult(value=None, is_percentage=False, warning_codes=["UNPARSABLE_NUMBER"])

        return NumberParseResult(value=None, is_percentage=False, warning_codes=["UNPARSABLE_NUMBER"])

    @staticmethod
    def normalize_scale(parsed_val: Decimal, scale: str) -> Decimal:
        """Apply scale multiplier using Decimal math. Raises UNSUPPORTED_SCALE on unknown scale."""
        sc_upper = scale.upper().strip() if scale else ""
        if sc_upper not in VALID_SCALES:
            raise ValueError(f"UNSUPPORTED_SCALE: Invalid or unknown scale '{scale}'")
        factor = SCALE_FACTORS[sc_upper]
        return parsed_val * factor

    @staticmethod
    def normalize_currency(currency: str) -> str:
        """Validate and return normalized uppercase currency code."""
        cur_upper = currency.upper().strip() if currency else ""
        if cur_upper not in VALID_CURRENCIES:
            raise ValueError(f"UNSUPPORTED_CURRENCY: Invalid or unknown currency '{currency}'")
        return cur_upper

    @staticmethod
    def normalize_unit(unit: str) -> str:
        """Validate and return normalized uppercase unit."""
        u_upper = unit.upper().strip() if unit else ""
        if u_upper not in VALID_UNITS:
            raise ValueError(f"UNSUPPORTED_UNIT: Invalid or unknown unit '{unit}'")
        return u_upper

    @staticmethod
    def validate_reporting_basis(reporting_basis: str) -> str:
        """Validate reporting basis. Raises UNSUPPORTED_REPORTING_BASIS on unknown/invalid basis."""
        b_upper = reporting_basis.upper().strip() if reporting_basis else ""
        if b_upper not in {"SOLO", "CONSOLIDATED"}:
            raise ValueError(f"UNSUPPORTED_REPORTING_BASIS: Invalid reporting basis '{reporting_basis}'")
        return b_upper

    @staticmethod
    def detect_reporting_basis(raw_text: str) -> str:
        """Detect SOLO vs CONSOLIDATED reporting basis."""
        if not raw_text:
            return "UNKNOWN"
        lower = raw_text.lower()
        if "konsolide olmayan" in lower or "solo" in lower or "unconsolidated" in lower:
            return "SOLO"
        if "konsolide" in lower or "consolidated" in lower:
            return "CONSOLIDATED"
        return "UNKNOWN"

    @staticmethod
    def validate_period_dates(start_date: date, end_date: date) -> bool:
        """Verify start_date <= end_date."""
        return start_date <= end_date

    @staticmethod
    def generate_comparison_key(period_type: str, fiscal_year: int, quarter: int | None = None) -> str:
        """Generate canonical comparison key (e.g. 2025-Q4, 2025-FY)."""
        if period_type == "QUARTER" and quarter:
            return f"{fiscal_year}-Q{quarter}"
        return f"{fiscal_year}-FY"
