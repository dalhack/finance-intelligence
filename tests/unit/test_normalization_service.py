from decimal import Decimal

import pytest

from services.api.app.services.normalization_service import NormalizationService


def test_parse_tr_locale_number():
    res = NormalizationService.parse_financial_decimal("1.234.567,89")
    assert res.value == Decimal("1234567.89")
    assert res.is_percentage is False
    assert res.warning_codes == []


def test_parse_en_locale_number():
    res = NormalizationService.parse_financial_decimal("1,234,567.89")
    assert res.value == Decimal("1234567.89")
    assert res.is_percentage is False
    assert res.warning_codes == []


def test_parse_negative_parentheses():
    res = NormalizationService.parse_financial_decimal("(1.250)")
    assert res.value == Decimal("-1250.00") or res.value == Decimal(-1250)


def test_parse_negative_sign():
    res = NormalizationService.parse_financial_decimal("-1.250")
    assert res.value == Decimal("-1250.00") or res.value == Decimal(-1250)


def test_parse_percentage():
    res = NormalizationService.parse_financial_decimal("%18,42")
    assert res.value == Decimal("18.42")
    assert res.is_percentage is True


def test_parse_dash_or_na():
    res1 = NormalizationService.parse_financial_decimal("—")
    assert res1.value is None
    assert "MISSING_VALUE" in res1.warning_codes

    res2 = NormalizationService.parse_financial_decimal("N/A")
    assert res2.value is None
    assert "MISSING_VALUE" in res2.warning_codes


def test_parse_empty_string():
    res = NormalizationService.parse_financial_decimal("   ")
    assert res.value is None
    assert "EMPTY_VALUE" in res.warning_codes


def test_parse_forbidden_exponent_notation():
    res = NormalizationService.parse_financial_decimal("1e5")
    assert res.value is None
    assert "FORBIDDEN_EXPONENT_OR_SPECIAL_FLOAT" in res.warning_codes


def test_normalize_scale():
    assert NormalizationService.normalize_scale(Decimal(2850), "THOUSAND") == Decimal(2850000)
    assert NormalizationService.normalize_scale(Decimal("1.5"), "MILLION") == Decimal("1500000.0")
    assert NormalizationService.normalize_scale(Decimal(2), "BILLION") == Decimal(2000000000)
    assert NormalizationService.normalize_scale(Decimal(100), "ONE") == Decimal(100)


def test_unsupported_scale_raises_exception():
    with pytest.raises(ValueError, match="UNSUPPORTED_SCALE"):
        NormalizationService.normalize_scale(Decimal(100), "TRILLION")


def test_unsupported_currency_raises_exception():
    assert NormalizationService.normalize_currency("TRY") == "TRY"
    with pytest.raises(ValueError, match="UNSUPPORTED_CURRENCY"):
        NormalizationService.normalize_currency("XYZ_UNKNOWN")


def test_unsupported_unit_raises_exception():
    assert NormalizationService.normalize_unit("CURRENCY") == "CURRENCY"
    with pytest.raises(ValueError, match="UNSUPPORTED_UNIT"):
        NormalizationService.normalize_unit("INVALID_UNIT")


def test_unsupported_reporting_basis_raises_exception():
    assert NormalizationService.validate_reporting_basis("SOLO") == "SOLO"
    assert NormalizationService.validate_reporting_basis("CONSOLIDATED") == "CONSOLIDATED"
    with pytest.raises(ValueError, match="UNSUPPORTED_REPORTING_BASIS"):
        NormalizationService.validate_reporting_basis("UNKNOWN")


def test_detect_reporting_basis():
    assert NormalizationService.detect_reporting_basis("Konsolide Bilanço") == "CONSOLIDATED"
    assert NormalizationService.detect_reporting_basis("Solo Finansal Rapor") == "SOLO"
    assert NormalizationService.detect_reporting_basis("Konsolide Olmayan Mali Tablo") == "SOLO"
    assert NormalizationService.detect_reporting_basis("Genel Rapor") == "UNKNOWN"


def test_period_comparison_key():
    assert NormalizationService.generate_comparison_key("QUARTER", 2025, 4) == "2025-Q4"
    assert NormalizationService.generate_comparison_key("YEAR", 2025) == "2025-FY"
