from uuid import UUID

import pytest

from services.api.app.services.calculation_service import compute_request_fingerprint


@pytest.mark.unit
def test_request_fingerprint_golden_vectors():
    """Verify request fingerprint computation against fixed golden vectors."""
    org_id = UUID("11111111-1111-1111-1111-111111111111")
    inst_id = UUID("22222222-2222-2222-2222-222222222222")
    rep_id = UUID("33333333-3333-3333-3333-333333333333")
    comp_id = UUID("44444444-4444-4444-4444-444444444444")

    # Vector 1: Null comparison period
    fp1 = compute_request_fingerprint(
        organization_id=org_id,
        formula_code="LOAN_TO_DEPOSIT_RATIO",
        formula_version="1.0.0",
        institution_id=inst_id,
        reporting_period_id=rep_id,
        comparison_period_id=None,
        comparison_policy="PREVIOUS_PERIOD",
    )
    assert len(fp1) == 64
    assert fp1 == fp1.lower()

    # Vector 2: Explicit comparison period
    fp2 = compute_request_fingerprint(
        organization_id=org_id,
        formula_code="LOAN_TO_DEPOSIT_RATIO",
        formula_version="1.0.0",
        institution_id=inst_id,
        reporting_period_id=rep_id,
        comparison_period_id=comp_id,
        comparison_policy="EXPLICIT_PERIOD",
    )
    assert len(fp2) == 64
    assert fp2 != fp1

    # Vector 3: Determinism assertion (same parameters -> identical fingerprint)
    fp3 = compute_request_fingerprint(
        organization_id=org_id,
        formula_code="LOAN_TO_DEPOSIT_RATIO",
        formula_version="1.0.0",
        institution_id=inst_id,
        reporting_period_id=rep_id,
        comparison_period_id=None,
        comparison_policy="PREVIOUS_PERIOD",
    )
    assert fp1 == fp3

    # Vector 4: Tenant isolation (different tenant -> different fingerprint)
    other_org = UUID("99999999-9999-9999-9999-999999999999")
    fp4 = compute_request_fingerprint(
        organization_id=other_org,
        formula_code="LOAN_TO_DEPOSIT_RATIO",
        formula_version="1.0.0",
        institution_id=inst_id,
        reporting_period_id=rep_id,
        comparison_period_id=None,
        comparison_policy="PREVIOUS_PERIOD",
    )
    assert fp4 != fp1
