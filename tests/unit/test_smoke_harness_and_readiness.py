import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_smoke_harness_script_exists():
    """Verify smoke harness script is present."""
    harness_path = REPO_ROOT / "scripts" / "run_local_ci_equivalence.py"
    assert harness_path.exists(), "run_local_ci_equivalence.py script missing!"


def test_release_readiness_artifact_structure():
    """Verify phase_4c2_release_readiness.json schema and gate status integrity."""
    artifact_path = REPO_ROOT / "artifacts" / "phase_4c2_release_readiness.json"
    assert artifact_path.exists()

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
        "READY_FOR_SINGLE_IOS_ONLY_REMOTE_REVALIDATION_AUTHORIZATION",
    )
    assert len(data["gates"]) >= 10

    allowed_statuses = {
        "PASS",
        "NOT_EXECUTED_AWAITING_USER_AUTHORIZATION",
        "DEFERRED_BY_USER",
        "FAIL",
    }
    for gate in data["gates"]:
        assert gate["status"] in allowed_statuses, f"Invalid gate status {gate['status']} in gate {gate['gateId']}"
