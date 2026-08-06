"""Unit tests for app.migration_execution.role_security module."""

import pytest
from app.migration_execution.role_security import (
    EXPECTED_ADMIN_SESSION_USER,
    EXPECTED_POSTCONDITION_CONTRACT,
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


def test_contract_drift_zero():
    """Verify EXPECTED_POSTCONDITION_CONTRACT matches exact 6-attribute least privilege tuple."""
    assert EXPECTED_POSTCONDITION_CONTRACT.rolcanlogin is True
    assert EXPECTED_POSTCONDITION_CONTRACT.rolsuper is False
    assert EXPECTED_POSTCONDITION_CONTRACT.rolcreaterole is False
    assert EXPECTED_POSTCONDITION_CONTRACT.rolcreatedb is False
    assert EXPECTED_POSTCONDITION_CONTRACT.rolbypassrls is False
    assert EXPECTED_POSTCONDITION_CONTRACT.rolreplication is False


def test_role_hardening_session_user_non_postgres_rejected(mocker):
    """Verify hardening fails closed if session_user is not 'postgres'."""
    mock_conn = mocker.MagicMock()
    mock_conn.in_transaction.return_value = False

    def mock_execute(statement, params=None):
        sql = str(statement).strip()
        result = mocker.MagicMock()
        if "session_user" in sql:
            result.scalar.return_value = "db_bootstrap"  # Non-postgres session_user
        return result

    mock_conn.execute.side_effect = mock_execute
    mock_engine = mocker.MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execution_options.return_value = mock_conn

    with pytest.raises(RoleHardeningError, match="Hardening must execute under session_user 'postgres'"):
        harden_application_login_roles(mock_engine)


def test_role_hardening_missing_target_role_fails_closed(mocker):
    """Verify hardening fails closed if a target role is missing from pg_roles."""
    mock_conn = mocker.MagicMock()
    mock_conn.in_transaction.return_value = False

    def mock_execute(statement, params=None):
        sql = str(statement).strip()
        result = mocker.MagicMock()
        if "session_user" in sql:
            result.scalar.return_value = EXPECTED_ADMIN_SESSION_USER
        elif "SELECT rolname" in sql:
            result.fetchall.return_value = [
                ("db_api_user", True, False, False, False, False, False),
                ("db_ingestion_worker", True, False, False, False, False, False),
                ("db_maintenance_worker", True, False, False, False, False, False),
            ]
        return result

    mock_conn.execute.side_effect = mock_execute
    mock_engine = mocker.MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execution_options.return_value = mock_conn

    with pytest.raises(RoleHardeningError, match="missing target role"):
        harden_application_login_roles(mock_engine)


def test_role_hardening_precondition_unsafe_superuser_rejected(mocker):
    """Verify hardening fails closed in precondition check if any target role is SUPERUSER."""
    mock_conn = mocker.MagicMock()
    mock_conn.in_transaction.return_value = False

    def mock_execute(statement, params=None):
        sql = str(statement).strip()
        result = mocker.MagicMock()
        if "session_user" in sql:
            result.scalar.return_value = EXPECTED_ADMIN_SESSION_USER
        elif "SELECT rolname" in sql:
            result.fetchall.return_value = [
                ("db_api_user", True, True, False, False, False, False),  # is_super=True
                ("db_ingestion_worker", True, False, False, False, False, False),
                ("db_maintenance_worker", True, False, False, False, False, False),
                ("db_bootstrap", True, False, False, False, False, False),
            ]
        return result

    mock_conn.execute.side_effect = mock_execute
    mock_engine = mocker.MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execution_options.return_value = mock_conn

    with pytest.raises(RoleHardeningError, match="Precondition failed!"):
        harden_application_login_roles(mock_engine)
