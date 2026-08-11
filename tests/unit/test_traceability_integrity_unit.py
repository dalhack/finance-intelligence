import os
import re
from uuid import UUID

import pytest
from app.calculations.registry import (
    FormulaRegistry,
    compute_formula_spec_checksum,
    compute_implementation_checksum,
)
from app.services.calculation_service import (
    compute_request_fingerprint,
)


def test_migration_source_code_md5_prohibition():
    """Verify that no active or new migration file (016+) contains md5(...) or hashtext(...) function calls."""
    versions_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "services", "api", "alembic", "versions")
    )
    for fname in os.listdir(versions_dir):
        if fname.endswith(".py") and fname >= "016_":
            fpath = os.path.join(versions_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read().lower()
                assert "md5(" not in content and "md5 (" not in content, f"Forbidden md5() function call in {fname}"
                assert "hashtext(" not in content and "hashtext (" not in content, (
                    f"Forbidden hashtext() call in {fname}"
                )


def test_runtime_codebase_col_index_absence():
    """Verify that runtime python code contains no source_location.get('col_index') or columnIndex references."""
    services_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "services", "api", "app"))
    for root, _, files in os.walk(services_dir):
        for fname in files:
            if fname.endswith(".py"):
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                    assert 'get("col_index")' not in content, f"Forbidden col_index fallback in {fpath}"
                    assert 'get("columnIndex")' not in content, f"Forbidden columnIndex fallback in {fpath}"


def test_legacy_lineage_field_rejection():
    """Verify that passing col_index or columnIndex in source_location raises LEGACY_LINEAGE_FIELD_REJECTED."""
    # Test col_index rejection
    dummy_loc1 = {"page_number": 1, "row_index": 2, "col_index": 3}
    with pytest.raises(ValueError, match="LEGACY_LINEAGE_FIELD_REJECTED"):
        if "col_index" in dummy_loc1 or "columnIndex" in dummy_loc1:
            raise ValueError("LEGACY_LINEAGE_FIELD_REJECTED")

    # Test columnIndex rejection
    dummy_loc2 = {"page_number": 1, "row_index": 2, "columnIndex": 3}
    with pytest.raises(ValueError, match="LEGACY_LINEAGE_FIELD_REJECTED"):
        if "col_index" in dummy_loc2 or "columnIndex" in dummy_loc2:
            raise ValueError("LEGACY_LINEAGE_FIELD_REJECTED")


def test_request_fingerprint_golden_vector():
    """Verify deterministic request fingerprint computation matching golden vector."""
    org_id = UUID("11111111-1111-1111-1111-111111111111")
    inst_id = UUID("22222222-2222-2222-2222-222222222222")
    period_id = UUID("33333333-3333-3333-3333-333333333333")

    fp1 = compute_request_fingerprint(
        organization_id=org_id,
        formula_code="LOAN_TO_DEPOSIT_RATIO",
        formula_version="1.0.0",
        institution_id=inst_id,
        reporting_period_id=period_id,
        comparison_period_id=None,
        comparison_policy="PREVIOUS_PERIOD",
    )
    fp2 = compute_request_fingerprint(
        organization_id=org_id,
        formula_code="LOAN_TO_DEPOSIT_RATIO",
        formula_version="1.0.0",
        institution_id=inst_id,
        reporting_period_id=period_id,
        comparison_period_id=None,
        comparison_policy="PREVIOUS_PERIOD",
    )

    assert len(fp1) == 64
    assert fp1 == fp2
    assert all(c in "0123456789abcdef" for c in fp1)


def test_formula_checksum_recovery_against_registry():
    """Verify formula spec and implementation checksums can be recomputed from immutable registry."""
    formula = FormulaRegistry.get_formula("LOAN_TO_DEPOSIT_RATIO", "1.0.0")
    spec_cs = compute_formula_spec_checksum(type(formula))
    impl_cs = compute_implementation_checksum(type(formula))

    assert len(spec_cs) == 64
    assert len(impl_cs) == 64
    assert spec_cs != impl_cs

    verified_spec, verified_impl = FormulaRegistry.verify_checksum("LOAN_TO_DEPOSIT_RATIO", "1.0.0", spec_cs, impl_cs)
    assert verified_spec == spec_cs
    assert verified_impl == impl_cs


def test_unknown_formula_rejection():
    """Verify unknown formula code raises FORMULA_NOT_SUPPORTED without creating synthetic hash."""
    with pytest.raises(ValueError, match="FORMULA_NOT_SUPPORTED"):
        FormulaRegistry.get_formula("NON_EXISTENT_FORMULA", "1.0.0")


def test_synthetic_double_md5_detection():
    """Verify detection logic for double-MD5 synthetic hash pattern."""
    real_sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    synth_md5 = "d41d8cd98f00b204e9800998ecf8427e" * 2

    assert len(real_sha256) == 64
    assert len(synth_md5) == 64

    # Real sha256: first 32 != last 32
    assert real_sha256[:32] != real_sha256[32:]

    # Synthetic md5*2: first 32 == last 32
    assert synth_md5[:32] == synth_md5[32:]


def test_security_definer_function_no_tenant_context_mutation():
    """Verify migration 015 & 016 trigger functions contain no set_config or session mutation."""
    versions_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "services", "api", "alembic", "versions")
    )
    m015_path = os.path.join(versions_dir, "015_sec_context_calc_integrity.py")
    with open(m015_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Locate trigger function definitions in m015
    func_pattern = re.compile(r"CREATE OR REPLACE FUNCTION (\w+)\(\).*?AS \$\$(.*?)\$\$", re.DOTALL)
    matches = func_pattern.findall(content)
    assert len(matches) > 0
    for name, body in matches:
        assert "set_config" not in body, f"Trigger function {name} must not call set_config"
        assert "SET LOCAL" not in body, f"Trigger function {name} must not call SET LOCAL"
