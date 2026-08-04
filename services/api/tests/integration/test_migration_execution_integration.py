"""Integration tests for Migration Execution Plane Handlers."""

from unittest.mock import MagicMock, patch

import pytest
from app.migration_execution.config import MigrationExecutionConfig


@pytest.fixture
def valid_config():
    return MigrationExecutionConfig(
        project_id="finance-intel-staging-8f2a",
        instance_name="fi-staging-db",
        region="europe-west1",
        target_database="finance_intelligence_staging",
        expected_head="030_reconcile_application_role_catalog",
        initial_admin_password="test_admin_pwd",
        bootstrap_password="test_bootstrap_pwd",
        api_password="test_api_pwd",
        worker_password="test_worker_pwd",
        maintenance_password="test_maint_pwd",
    )


@patch("app.migration_execution.provisioning.create_user_if_missing")
@patch("app.migration_execution.provisioning.get_cloudsql_engine")
def test_provision_application_database_flow(mock_get_engine, mock_create_user, valid_config):
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_get_engine.return_value = (mock_engine, MagicMock())
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Simulate database not existing initially
    mock_conn.execute.return_value.scalar.return_value = None

    from app.migration_execution.provisioning import provision_application_database

    provision_application_database(valid_config)

    assert mock_create_user.call_count == 4
    assert mock_conn.execute.call_count >= 5


@patch("app.migration_execution.alembic_runner.command.upgrade")
@patch("app.migration_execution.alembic_runner.create_engine")
@patch("app.migration_execution.alembic_runner.Connector")
def test_run_alembic_migrations_flow(mock_connector_cls, mock_create_engine, mock_upgrade, valid_config):
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Simulate active role check and alembic version query
    mock_conn.execute.side_effect = [
        MagicMock(),  # SET ROLE db_owner
        MagicMock(fetchone=lambda: ("db_bootstrap", "db_owner")),  # SELECT session_user, current_user
        MagicMock(),  # pg_advisory_lock
        MagicMock(fetchone=lambda: ("030_reconcile_application_role_catalog",)),  # alembic_version query
        MagicMock(),  # pg_advisory_unlock
    ]

    from app.migration_execution.alembic_runner import run_alembic_migrations

    run_alembic_migrations(valid_config)

    assert mock_upgrade.call_count == 1


@patch("app.migration_execution.verification.create_engine")
@patch("app.migration_execution.verification.Connector")
def test_run_security_verification_gates_flow(mock_connector_cls, mock_create_engine, valid_config):
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Mock responses for 11 verification gates
    mock_conn.execute.side_effect = [
        MagicMock(fetchone=lambda: ("030_reconcile_application_role_catalog",)),  # Gate 1
        MagicMock(fetchone=lambda: ("db_owner",)),  # Gate 2
        # Gate 3: Roles
        MagicMock(fetchone=lambda: (False, False, False, False)),
        MagicMock(fetchone=lambda: (False, False, False, False)),
        MagicMock(fetchone=lambda: (False, False, False, False)),
        MagicMock(fetchone=lambda: (False, False, False, False)),
        MagicMock(fetchone=lambda: (False, False, False, False)),
        # Gate 4: Membership
        MagicMock(fetchone=lambda: (1,)),
        # Gate 5: Runtime isolation
        MagicMock(fetchone=lambda: None),
        MagicMock(fetchone=lambda: None),
        MagicMock(fetchone=lambda: None),
        # Gate 6: RLS for 15 domain tables
        *[MagicMock(fetchone=lambda: (True, True)) for _ in range(15)],
        # Gate 7: Schema ACL
        MagicMock(fetchone=lambda: (False,)),
        # Gate 8: SECURITY DEFINER
        MagicMock(fetchone=lambda: (True, "db_owner", None)),
        # Gate 9: Permission count
        MagicMock(fetchone=lambda: (17,)),
        # Gate 10: Role catalog counts
        MagicMock(fetchall=lambda: [("VIEWER", 8), ("ANALYST", 15)]),
        # Gate 11: Uppercase constraint
        MagicMock(fetchone=lambda: (1,)),
    ]

    from app.migration_execution.verification import run_security_verification

    run_security_verification(valid_config)
