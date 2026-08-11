import hashlib
import json
from typing import Any, ClassVar

from app.calculations.base import BaseFormula
from app.calculations.formulas.growth_rate import GrowthRateFormula
from app.calculations.formulas.loan_to_deposit import LoanToDepositRatioFormula
from app.calculations.formulas.npl_ratio import NplRatioFormula
from app.calculations.formulas.return_on_assets import ReturnOnAssetsFormula
from app.calculations.formulas.return_on_equity import ReturnOnEquityFormula


def is_valid_sha256_hex(val: Any) -> bool:
    """Validate exact 64-character lowercase hex format."""
    if not isinstance(val, str) or len(val) != 64:
        return False
    return all(c in "0123456789abcdef" for c in val)


def compute_formula_spec_checksum(formula_cls: type[BaseFormula]) -> str:
    """Compute Layer 1 formula_spec_checksum from canonical specification metadata."""
    canonical_payload = {
        "formula_code": formula_cls.formula_code,
        "formula_version": formula_cls.formula_version,
        "required_input_roles": sorted(formula_cls.required_input_roles),
        "expected_metric_codes": sorted(formula_cls.expected_metric_codes),
        "result_unit": formula_cls.result_unit,
        "result_scale": formula_cls.result_scale,
        "rounding_policy": formula_cls.rounding_policy,
        "annualization_policy": formula_cls.annualization_policy,
        "display_precision": formula_cls.display_precision,
        "tolerance_kind": formula_cls.tolerance_kind,
        "tolerance_value": str(formula_cls.tolerance_value),
        "tolerance_unit": formula_cls.tolerance_unit,
        "tolerance_policy_version": formula_cls.tolerance_policy_version,
        "comparison_requirement": formula_cls.comparison_requirement,
    }
    raw_bytes = json.dumps(canonical_payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


def compute_implementation_checksum(formula_cls: type[BaseFormula]) -> str:
    """Compute Layer 2 implementation_checksum from immutable revision & algorithm fingerprint."""
    canonical_payload = {
        "formula_code": formula_cls.formula_code,
        "formula_version": formula_cls.formula_version,
        "implementation_revision": formula_cls.implementation_revision,
        "algorithm_fingerprint": formula_cls.algorithm_fingerprint,
    }
    raw_bytes = json.dumps(canonical_payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


class FormulaRegistry:
    _registry: ClassVar[dict[tuple[str, str], type[BaseFormula]]] = {
        ("GROWTH_RATE", "1.0.0"): GrowthRateFormula,
        ("LOAN_TO_DEPOSIT_RATIO", "1.0.0"): LoanToDepositRatioFormula,
        ("NPL_RATIO", "1.0.0"): NplRatioFormula,
        ("RETURN_ON_ASSETS", "1.0.0"): ReturnOnAssetsFormula,
        ("RETURN_ON_EQUITY", "1.0.0"): ReturnOnEquityFormula,
    }

    @classmethod
    def get_formula(cls, formula_code: str, formula_version: str = "1.0.0") -> BaseFormula:
        if formula_code in ("NET_INTEREST_MARGIN", "CAPITAL_ADEQUACY_RATIO"):
            raise ValueError("FORMULA_INPUT_METRIC_UNAVAILABLE")

        key = (formula_code, formula_version)
        formula_cls = cls._registry.get(key)
        if not formula_cls:
            matching_codes = [c for c, v in cls._registry if c == formula_code]
            if matching_codes:
                raise ValueError("FORMULA_VERSION_MISMATCH")
            raise ValueError("FORMULA_NOT_SUPPORTED")

        return formula_cls()

    @classmethod
    def verify_checksum(
        cls,
        formula_code: str,
        formula_version: str,
        db_spec_checksum: str | None = None,
        db_impl_checksum: str | None = None,
    ) -> tuple[str, str]:
        """Verify formula specification and implementation checksums fail-closed.

        Requires exact 64-character lowercase hex format for both spec and impl checksums.
        Raises FORMULA_VERSION_MISMATCH if checksums are null, empty, malformed, or mismatched.
        """
        key = (formula_code, formula_version)
        formula_cls = cls._registry.get(key)
        if not formula_cls:
            raise ValueError("FORMULA_NOT_SUPPORTED")

        code_spec_checksum = compute_formula_spec_checksum(formula_cls)
        code_impl_checksum = compute_implementation_checksum(formula_cls)

        if not is_valid_sha256_hex(db_spec_checksum) or db_spec_checksum != code_spec_checksum:
            raise ValueError("FORMULA_VERSION_MISMATCH")

        if not is_valid_sha256_hex(db_impl_checksum) or db_impl_checksum != code_impl_checksum:
            raise ValueError("FORMULA_VERSION_MISMATCH")

        return code_spec_checksum, code_impl_checksum
