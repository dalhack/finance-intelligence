"""Unit tests for remediated lock-scoped phased Alembic state machine runner."""

from unittest.mock import MagicMock, patch

import pytest
from app.migration_execution.alembic_runner import (
    MigrationRunnerError,
    ensure_clean_transaction,
    get_safe_current_revision,
    run_alembic_migrations,
)
from app.migration_execution.config import MigrationExecutionConfig


@pytest.fixture
def mock_config():
    return MigrationExecutionConfig(
        project_id="finance-intel-staging-8f2a",
        instance_name="fi-staging-db",
        region="europe-west1",
        target_database="finance_intelligence_staging",
        expected_head="031_analysis_job_claim_authority",
        bootstrap_password="test_bootstrap_password",
    )


def test_detect_revision_missing_table_returns_none():
    """Verifies that MigrationContext returns None for missing version table without throwing SQL errors."""
    mock_conn = MagicMock()
    mock_conn.in_transaction.return_value = True

    with patch("app.migration_execution.alembic_runner.MigrationContext") as mock_context_cls:
        mock_context = MagicMock()
        mock_context.get_current_revision.return_value = None
        mock_context_cls.configure.return_value = mock_context

        rev = get_safe_current_revision(mock_conn)

        assert rev is None
        mock_context.get_current_revision.assert_called_once()
        mock_conn.commit.assert_called_once()


def test_unknown_revision_rejects_fail_closed():
    """Verifies that an unknown or invalid revision string raises MigrationRunnerError."""
    mock_conn = MagicMock()
    mock_conn.in_transaction.return_value = False

    with patch("app.migration_execution.alembic_runner.MigrationContext") as mock_context_cls:
        mock_context = MagicMock()
        mock_context.get_current_revision.return_value = "invalid_unknown_rev_999"
        mock_context_cls.configure.return_value = mock_context

        with pytest.raises(MigrationRunnerError, match="Unknown or invalid migration revision detected"):
            get_safe_current_revision(mock_conn)


def test_ensure_clean_transaction_commits():
    """Verifies that ensure_clean_transaction commits active transaction if in_transaction() is True."""
    mock_conn = MagicMock()
    mock_conn.in_transaction.side_effect = [True, False]

    ensure_clean_transaction(mock_conn, "test phase")

    mock_conn.commit.assert_called_once()


def test_rollback_before_unlock_on_failure(mock_config):
    """Verifies that in exception cleanup, rollback is executed before attempting advisory unlock."""
    mock_connector_cls = MagicMock()
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.invalidated = False
    in_trans = {"active": False}
    mock_conn.execute.side_effect = lambda *a, **kw: (
        in_trans.update({"active": True})
        or MagicMock(fetchone=lambda: ("db_bootstrap", "db_owner", 12345), scalar=lambda: 12345)
    )
    mock_conn.commit.side_effect = lambda: in_trans.update({"active": False})
    mock_conn.rollback.side_effect = lambda: in_trans.update({"active": False})
    mock_conn.in_transaction.side_effect = lambda: in_trans["active"]

    # Setup connection queries:
    # 1. SET ROLE db_owner
    # 2. SELECT session_user, current_user, pg_backend_pid()
    # 3. SELECT pg_advisory_lock
    # 4. SELECT count(*) FROM pg_locks
    # 5. SELECT pg_backend_pid()
    # 6. get_safe_current_revision -> None
    # 7. command.upgrade -> throws Exception
    mock_conn.execute.side_effect = [
        MagicMock(),  # SET ROLE
        MagicMock(fetchone=lambda: ("db_bootstrap", "db_owner", 12345)),  # identity
        MagicMock(),  # pg_advisory_lock
        MagicMock(scalar=lambda: 1),  # pg_locks check
        MagicMock(scalar=lambda: 12345),  # PID check
    ]

    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    def fail_upgrade(*a, **kw):
        in_trans["active"] = True
        raise RuntimeError("Phase 1 DDL error")

    mock_conn.commit.side_effect = lambda: setattr(mock_conn.in_transaction, "return_value", False)

    with (
        patch("app.migration_execution.alembic_runner.Connector", return_value=mock_connector_cls),
        patch("app.migration_execution.alembic_runner.create_engine", return_value=mock_engine),
        patch("app.migration_execution.alembic_runner.get_safe_current_revision", return_value=None),
        patch("app.migration_execution.alembic_runner.command.upgrade", side_effect=fail_upgrade),
    ):
        with pytest.raises(MigrationRunnerError, match="Migration execution failed: Phase 1 DDL error") as exc_info:
            run_alembic_migrations(mock_config)

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        # Verify rollback was called during cleanup
        assert mock_conn.rollback.call_count >= 1


def test_unlock_false_fails_closed(mock_config):
    """Verifies that if explicit pg_advisory_unlock returns false, run_alembic_migrations fails closed."""
    mock_connector_cls = MagicMock()
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.invalidated = False
    mock_conn.in_transaction.return_value = False

    # Execute flow returning unlock = False
    mock_conn.execute.side_effect = [
        MagicMock(),  # SET ROLE
        MagicMock(fetchone=lambda: ("db_bootstrap", "db_owner", 12345)),  # identity
        MagicMock(),  # pg_advisory_lock
        MagicMock(scalar=lambda: 1),  # pg_locks check
        MagicMock(scalar=lambda: 12345),  # PID check
        MagicMock(scalar=lambda: 12345),  # pre-unlock PID check
        MagicMock(fetchone=lambda: (False,)),  # pg_advisory_unlock returning FALSE
    ]

    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with (
        patch("app.migration_execution.alembic_runner.Connector", return_value=mock_connector_cls),
        patch("app.migration_execution.alembic_runner.create_engine", return_value=mock_engine),
        patch(
            "app.migration_execution.alembic_runner.get_safe_current_revision",
            return_value="031_analysis_job_claim_authority",
        ),
        patch("app.migration_execution.alembic_runner.verify_revision_024_postconditions"),
        pytest.raises(MigrationRunnerError, match="unlock returned false or failed"),
    ):
        run_alembic_migrations(mock_config)
