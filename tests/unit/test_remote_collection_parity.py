"""Contract test verifying test collection parity and canonical import identity between remote CI and local test roots."""

import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[2] / "services" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def test_ci_workflow_collects_services_api_test_root():
    """Verifies that ci.yml includes services/api/tests/unit in pytest command."""
    ci_yml = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
    assert ci_yml.exists(), "ci.yml workflow file missing"
    content = ci_yml.read_text(encoding="utf-8")

    assert "services/api/tests/unit" in content, (
        "CRITICAL: ci.yml must explicitly collect services/api/tests/unit in pytest step"
    )
    assert "PYTHONPATH:" in content and "services/api" in content, (
        "CRITICAL: ci.yml must set PYTHONPATH to include services/api"
    )


def test_canonical_import_identity_contract():
    """Verifies that alembic_runner is loaded under canonical 'app' module prefix."""
    from app.migration_execution import alembic_runner

    # 1. Canonical module identity check
    assert alembic_runner.__name__ == "app.migration_execution.alembic_runner"

    # 2. Assert patch target identity matches production module callable identity
    from app.migration_execution.alembic_runner import run_alembic_migrations

    assert run_alembic_migrations.__module__ == "app.migration_execution.alembic_runner", (
        "Callable module identity mismatch"
    )
