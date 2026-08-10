"""Contract test verifying test collection parity between remote CI and local test roots."""

from pathlib import Path

# Re-export critical least-privilege remediation unit tests to guarantee execution under pytest tests/unit
from services.api.tests.unit.test_migration_runner_remediation import (
    test_historical_migration_026_unmodified,
    test_least_privilege_no_grant_if_create_already_exists,
    test_least_privilege_revoke_on_migration_failure,
    test_least_privilege_temporary_grant_and_revoke_success,
    test_logging_exit_path_flushes_all_streams,
)

__all__ = [
    "test_historical_migration_026_unmodified",
    "test_least_privilege_no_grant_if_create_already_exists",
    "test_least_privilege_revoke_on_migration_failure",
    "test_least_privilege_temporary_grant_and_revoke_success",
    "test_logging_exit_path_flushes_all_streams",
]


def test_ci_workflow_collects_services_api_test_root():
    """Verifies that ci.yml includes services/api/tests/unit in pytest command."""
    ci_yml = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
    assert ci_yml.exists(), "ci.yml workflow file missing"
    content = ci_yml.read_text(encoding="utf-8")

    assert "services/api/tests/unit" in content, (
        "CRITICAL: ci.yml must explicitly collect services/api/tests/unit in pytest step"
    )
