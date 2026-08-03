import json
import os

import pytest

from services.api.app.orchestration.smoke_test_harness import SmokeTestHarness


def test_smoke_harness_dry_run_execution():
    """Verify SmokeTestHarness dry-run behavior performs zero network calls."""
    harness = SmokeTestHarness(dry_run=True, allow_paid_call=False)
    result = harness.execute_harness()

    assert result["status"] == "DRY_RUN_SUCCESS"
    assert result["network_calls"] == 0
    assert result["secret_handle"] == "RESOLVED_SYNTHETIC"
    assert result["dry_run"] is True


def test_smoke_harness_paid_call_rejection_without_artifact():
    """Verify SmokeTestHarness rejects allow_paid_call without valid authorization artifact."""
    harness = SmokeTestHarness(dry_run=False, allow_paid_call=True, authorization_artifact_path=None)
    with pytest.raises(ValueError, match="PAID_CALL_NOT_AUTHORIZED"):
        harness.execute_harness()


def test_smoke_harness_paid_call_rejection_with_example_artifact():
    """Verify SmokeTestHarness rejects example authorization artifact fail-closed."""
    example_path = "/Users/korhanturgut/.gemini/antigravity-ide/scratch/finance-intelligence/artifacts/paid_provider_smoke_test_authorization.example.json"
    assert os.path.exists(example_path)

    harness = SmokeTestHarness(dry_run=False, allow_paid_call=True, authorization_artifact_path=example_path)
    with pytest.raises(ValueError, match="PAID_CALL_NOT_AUTHORIZED"):
        harness.execute_harness()


def test_release_readiness_artifact_structure():
    """Verify phase_4c2_release_readiness.json schema and gate status integrity."""
    artifact_path = "/Users/korhanturgut/.gemini/antigravity-ide/scratch/finance-intelligence/artifacts/phase_4c2_release_readiness.json"
    assert os.path.exists(artifact_path)

    with open(artifact_path) as f:
        data = json.load(f)

    assert data["targetPhase"] in (
        "PHASE_4C_2C",
        "PHASE_4C_2C_1",
        "PHASE_4C_2C_2",
        "PHASE_4C_2C_3",
        "PHASE_4C_2C_4",
        "PHASE_4C_2C_5",
        "PHASE_4C_2C_EXECUTION",
    )
    assert data["finalDecision"] in (
        "READY_FOR_EXTERNAL_VALIDATION_REVIEW",
        "READY_FOR_EXTERNAL_AUTHORIZATION_DECISIONS",
        "BLOCKED_BEFORE_EXTERNAL_AUTHORIZATION_DECISIONS",
        "AWAITING_USER_AUTHORIZATION_FOR_REMOTE_IOS_CI",
        "REMOTE_IOS_VALIDATION_BLOCKED_BY_AUTHORIZATION_OR_REMOTE_ACCESS",
        "REMOTE_IOS_VALIDATION_BLOCKED_BY_GITHUB_ACCESS",
        "REMOTE_IOS_VALIDATION_FAILED_REVIEW_REQUIRED",
    )
    assert len(data["gates"]) >= 10

    allowed_statuses = {
        "PASS",
        "FAIL",
        "BLOCKED",
        "BLOCKED_BY_TOOLCHAIN",
        "BLOCKED_AMBIGUOUS_REMOTE",
        "BLOCKED_BY_REMOTE_ACCESS",
        "BLOCKED_BY_GITHUB_ACCESS",
        "UNVERIFIED",
        "NOT_IMPLEMENTED",
        "NOT_AUTHORIZED",
        "PENDING_REVIEW",
        "NOT_CONFIGURED",
        "DEFERRED_BY_USER",
    }
    for gate in data["gates"]:
        assert gate["status"] in allowed_statuses
