"""Unit tests for app.migration_execution.role_security module."""

import pytest
from app.migration_execution.role_security import (
    FORBIDDEN_TARGET_ROLES,
    HARDENING_TARGET_ALLOWLIST,
    RoleHardeningError,
    harden_application_login_roles,
)


def test_target_allowlist_ordering_and_contents():
    """Verify hardening target allowlist contains exact 4 roles in exact order (db_bootstrap LAST)."""
    assert HARDENING_TARGET_ALLOWLIST == (
        "db_api_user",
        "db_ingestion_worker",
        "db_maintenance_worker",
        "db_bootstrap",
    )
    assert HARDENING_TARGET_ALLOWLIST[-1] == "db_bootstrap"


def test_forbidden_roles():
    """Verify postgres, db_owner, db_app_user are explicitly forbidden as targets."""
    for role in ("postgres", "db_owner", "db_app_user"):
        assert role in FORBIDDEN_TARGET_ROLES


def test_role_hardening_missing_target_role_fails_closed(mocker):
    """Verify hardening fails closed if a target role is missing from pg_roles."""
    mock_conn = mocker.MagicMock()
    mock_conn.in_transaction.return_value = False

    # Simulate session_user = postgres, but only 3 roles exist (db_bootstrap missing)
    def mock_execute(statement, params=None):
        sql = str(statement).strip()
        result = mocker.MagicMock()
        if "session_user" in sql:
            result.scalar.return_value = "postgres"
        elif "SELECT rolname FROM pg_roles" in sql:
            result.scalars().all.return_value = ["db_api_user", "db_ingestion_worker", "db_maintenance_worker"]
        return result

    mock_conn.execute.side_effect = mock_execute
    mock_engine = mocker.MagicMock()
    mock_engine.execution_options.return_value.connect.return_value.__enter__.return_value = mock_conn

    with pytest.raises(RoleHardeningError, match="missing target role"):
        harden_application_login_roles(mock_engine)
