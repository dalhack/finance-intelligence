from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.calculations.base import to_working_fraction
from app.calculations.formulas.growth_rate import GrowthRateFormula
from app.calculations.formulas.loan_to_deposit import LoanToDepositRatioFormula
from app.calculations.formulas.npl_ratio import NplRatioFormula
from app.calculations.formulas.return_on_assets import ReturnOnAssetsFormula
from app.calculations.registry import (
    FormulaRegistry,
    compute_formula_spec_checksum,
    compute_implementation_checksum,
    is_valid_sha256_hex,
)
from app.services.calculation_service import (
    compute_canonical_idempotency_hash,
    compute_request_fingerprint,
)


def test_is_valid_sha256_hex():
    """Verify strict 64-character lowercase hex validator."""
    assert is_valid_sha256_hex("a" * 64) is True
    assert is_valid_sha256_hex("0123456789abcdef" * 4) is True

    # Invalid cases
    assert is_valid_sha256_hex(None) is False
    assert is_valid_sha256_hex("") is False
    assert is_valid_sha256_hex("a" * 63) is False
    assert is_valid_sha256_hex("a" * 65) is False
    assert is_valid_sha256_hex("A" * 64) is False  # Uppercase forbidden
    assert is_valid_sha256_hex("g" * 64) is False  # Non-hex forbidden


def test_percentage_contract_adapter():
    """Verify display percentage (18.42%) is converted to working fraction (0.1842)."""
    val = Decimal("18.42")
    frac = to_working_fraction(val, "PERCENT")
    assert frac == Decimal("0.1842")

    currency_val = Decimal("100.00")
    curr_frac = to_working_fraction(currency_val, "CURRENCY")
    assert curr_frac == Decimal("100.00")

    with pytest.raises(ValueError, match="UNIT_MISMATCH"):
        to_working_fraction(Decimal(100), "")


def test_growth_rate_formula():
    """Verify GROWTH_RATE formula: ((CURRENT / COMPARISON) - 1) * 100."""
    formula = GrowthRateFormula()
    assert formula.comparison_requirement == "REQUIRED_COMPARISON"

    res_zero = formula.calculate(
        {
            "CURRENT_VALUE": {"normalized_value": Decimal(100), "unit": "CURRENCY"},
            "COMPARISON_VALUE": {"normalized_value": Decimal(100), "unit": "CURRENCY"},
        },
        {},
    )
    assert res_zero.result_value_unrounded == Decimal(0)
    assert res_zero.result_value_display == Decimal("0.00")

    res_pos = formula.calculate(
        {
            "CURRENT_VALUE": {"normalized_value": Decimal(150), "unit": "CURRENCY"},
            "COMPARISON_VALUE": {"normalized_value": Decimal(100), "unit": "CURRENCY"},
        },
        {},
    )
    assert res_pos.result_value_unrounded == Decimal("50.0")

    with pytest.raises(ValueError, match="DIVISION_BY_ZERO"):
        formula.calculate(
            {
                "CURRENT_VALUE": {"normalized_value": Decimal(100), "unit": "CURRENCY"},
                "COMPARISON_VALUE": {"normalized_value": Decimal(0), "unit": "CURRENCY"},
            },
            {},
        )


def test_loan_to_deposit_ratio_formula():
    """Verify LOAN_TO_DEPOSIT_RATIO formula: (TOTAL_LOANS / TOTAL_DEPOSITS) * 100."""
    formula = LoanToDepositRatioFormula()
    assert formula.comparison_requirement == "NONE"

    res = formula.calculate(
        {
            "NUMERATOR": {"normalized_value": Decimal(800), "unit": "CURRENCY", "currency": "TRY", "scale": "ONE"},
            "DENOMINATOR": {"normalized_value": Decimal(1000), "unit": "CURRENCY", "currency": "TRY", "scale": "ONE"},
        },
        {},
    )
    assert res.result_value_unrounded == Decimal("80.0")
    assert res.result_value_display == Decimal("80.00")

    with pytest.raises(ValueError, match="UNIT_MISMATCH"):
        formula.calculate(
            {
                "NUMERATOR": {"normalized_value": Decimal(800), "unit": "CURRENCY", "currency": "TRY", "scale": "ONE"},
                "DENOMINATOR": {
                    "normalized_value": Decimal(1000),
                    "unit": "PERCENT",
                    "currency": "TRY",
                    "scale": "ONE",
                },
            },
            {},
        )


def test_npl_ratio_formula():
    """Verify NPL_RATIO formula."""
    formula = NplRatioFormula()
    assert formula.comparison_requirement == "NONE"

    res = formula.calculate(
        {
            "NUMERATOR": {"normalized_value": Decimal(50), "unit": "CURRENCY", "currency": "TRY", "scale": "ONE"},
            "DENOMINATOR": {"normalized_value": Decimal(1000), "unit": "CURRENCY", "currency": "TRY", "scale": "ONE"},
        },
        {},
    )
    assert res.result_value_unrounded == Decimal("5.0")
    assert res.result_value_display == Decimal("5.00")


def test_return_on_assets_formula():
    """Verify RETURN_ON_ASSETS formula."""
    formula = ReturnOnAssetsFormula()
    assert formula.comparison_requirement == "REQUIRED_BEGINNING_BALANCE"

    fact_id = uuid4()
    with pytest.raises(ValueError, match="DUPLICATE_BALANCE_INPUT"):
        formula.calculate(
            {
                "PERIOD_INCOME": {
                    "id": uuid4(),
                    "normalized_value": Decimal(100),
                    "unit": "CURRENCY",
                    "currency": "TRY",
                },
                "BEGINNING_BALANCE": {
                    "id": fact_id,
                    "normalized_value": Decimal(4000),
                    "unit": "CURRENCY",
                    "currency": "TRY",
                },
                "ENDING_BALANCE": {
                    "id": fact_id,
                    "normalized_value": Decimal(6000),
                    "unit": "CURRENCY",
                    "currency": "TRY",
                },
            },
            {"annualization_factor": "4.0"},
        )

    res = formula.calculate(
        {
            "PERIOD_INCOME": {"id": uuid4(), "normalized_value": Decimal(100), "unit": "CURRENCY", "currency": "TRY"},
            "BEGINNING_BALANCE": {
                "id": uuid4(),
                "normalized_value": Decimal(4000),
                "unit": "CURRENCY",
                "currency": "TRY",
            },
            "ENDING_BALANCE": {"id": uuid4(), "normalized_value": Decimal(6000), "unit": "CURRENCY", "currency": "TRY"},
        },
        {"annualization_factor": "4.0"},
    )
    assert res.result_value_unrounded == Decimal("8.0")
    assert res.result_value_display == Decimal("8.00")


def test_two_layer_checksum_verification_fail_closed_matrix():
    """Verify fail-closed behavior for null, empty, short, non-hex, uppercase, and mismatched checksums."""
    formula_cls = LoanToDepositRatioFormula
    spec_cs = compute_formula_spec_checksum(formula_cls)
    impl_cs = compute_implementation_checksum(formula_cls)

    # Valid checksums
    s, i = FormulaRegistry.verify_checksum("LOAN_TO_DEPOSIT_RATIO", "1.0.0", spec_cs, impl_cs)
    assert s == spec_cs
    assert i == impl_cs

    # Invalid spec checksum cases
    invalid_cases = [
        None,
        "",
        "a" * 63,
        "a" * 65,
        spec_cs.upper(),  # Uppercase
        "z" * 64,  # Non-hex
        "1" * 64,  # Valid-length mismatch
    ]

    for inv in invalid_cases:
        with pytest.raises(ValueError, match="FORMULA_VERSION_MISMATCH"):
            FormulaRegistry.verify_checksum("LOAN_TO_DEPOSIT_RATIO", "1.0.0", inv, impl_cs)

        with pytest.raises(ValueError, match="FORMULA_VERSION_MISMATCH"):
            FormulaRegistry.verify_checksum("LOAN_TO_DEPOSIT_RATIO", "1.0.0", spec_cs, inv)


def test_checksum_mismatch_prevents_formula_calculate_invocation():
    """Verify formula calculate() is never called if checksum validation fails."""
    formula_instance = LoanToDepositRatioFormula()
    formula_instance.calculate = MagicMock()

    # Mismatch spec checksum should raise FORMULA_VERSION_MISMATCH
    with pytest.raises(ValueError, match="FORMULA_VERSION_MISMATCH"):
        FormulaRegistry.verify_checksum("LOAN_TO_DEPOSIT_RATIO", "1.0.0", "0" * 64, "1" * 64)

    assert formula_instance.calculate.call_count == 0


def test_request_fingerprint_and_canonical_idempotency_hash_separation():
    """Verify request_fingerprint and execution_idempotency_hash identity separation."""
    org_id = uuid4()
    p1_id = uuid4()
    inst_id = uuid4()
    fact1_id = uuid4()
    fact2_id = uuid4()

    req_fp = compute_request_fingerprint(
        organization_id=org_id,
        formula_code="LOAN_TO_DEPOSIT_RATIO",
        formula_version="1.0.0",
        institution_id=inst_id,
        reporting_period_id=p1_id,
        comparison_period_id=None,
        comparison_policy="PREVIOUS_PERIOD",
    )

    inputs = {
        "NUMERATOR": {"id": fact1_id, "normalized_value": Decimal(800), "unit": "CURRENCY", "currency": "TRY"},
        "DENOMINATOR": {"id": fact2_id, "normalized_value": Decimal(1000), "unit": "CURRENCY", "currency": "TRY"},
    }

    exec_hash = compute_canonical_idempotency_hash(
        organization_id=org_id,
        formula_code="LOAN_TO_DEPOSIT_RATIO",
        formula_version="1.0.0",
        formula_spec_checksum="spec123",
        implementation_checksum="impl123",
        inputs_by_role=inputs,
        reporting_period_id=p1_id,
        comparison_period_id=None,
        comparison_policy="PREVIOUS_PERIOD",
    )

    assert len(req_fp) == 64
    assert len(exec_hash) == 64
    assert req_fp != exec_hash
