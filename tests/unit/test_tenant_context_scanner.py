import pytest

from scripts.verify_tenant_context_scoping import scan_tenant_context_scoping


@pytest.mark.unit
def test_zero_tenant_context_false_violations():
    """Automated unit scanner asserting zero set_config(..., false) non-transactional calls across codebase."""
    violations = scan_tenant_context_scoping()
    assert len(violations) == 0, f"Found non-transactional tenant context violations: {violations}"
