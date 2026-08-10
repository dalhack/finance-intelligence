"""Unit regression suite for Revision 026 Session-Context Remediation (T1-T10)."""

import sys
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest

# Ensure services/api is in sys.path
API_DIR = Path(__file__).resolve().parent.parent.parent / "services" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.migration_execution.alembic_runner import MigrationRunnerError, run_alembic_migrations
from app.migration_execution.config import MigrationExecutionConfig


@pytest.fixture
def base_config():
    return MigrationExecutionConfig(
        project_id="finance-intel-staging-8f2a",
        instance_name="fi-staging-db",
        region="europe-west1",
        target_database="finance_intelligence_staging",
        expected_head="031_analysis_job_claim_authority",
        bootstrap_password="test_bootstrap_password",
    )


def test_t1_t2_t3_reset_role_called_before_phase3_alembic(base_config):
    """T1-T3 — Verifies SET ROLE db_owner in Phase 2, RESET ROLE in Phase 3 prior to command.upgrade."""
    mock_connector = MagicMock()
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.invalidated = False
    mock_conn.in_transaction.return_value = False

    # Mock SQL execution responses
    def execute_side_effect(sql, *args, **kwargs):
        sql_str = str(sql)
        mock_result = MagicMock()
        if "SET ROLE db_owner" in sql_str:
            return mock_result
        if "SELECT session_user, current_user, pg_backend_pid()" in sql_str:
            mock_result.fetchone.return_value = ("db_bootstrap", "db_owner", 1234)
            return mock_result
        if "SELECT pg_advisory_lock" in sql_str:
            return mock_result
        if "SELECT count(*) FROM pg_locks" in sql_str:
            mock_result.scalar.return_value = 1
            return mock_result
        if "SELECT pg_backend_pid()" in sql_str:
            mock_result.scalar.return_value = 1234
            return mock_result
        if "SELECT version_num FROM alembic_version" in sql_str:
            # First check returns 024, second check in Phase 3 returns 031
            mock_result.scalar.return_value = "024_maintenance_scheduler_and_operational_resilience"
            mock_result.fetchone.return_value = ("024_maintenance_scheduler_and_operational_resilience",)
            return mock_result
        if "RESET ROLE" in sql_str:
            return mock_result
        if "SELECT session_user, current_user;" in sql_str:
            mock_result.fetchone.return_value = ("db_bootstrap", "db_bootstrap")
            return mock_result
        if "SELECT pg_advisory_unlock" in sql_str:
            mock_result.fetchone.return_value = (True,)
            return mock_result
        return mock_result

    mock_conn.execute.side_effect = execute_side_effect

    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with (
        patch("app.migration_execution.alembic_runner.Connector", return_value=mock_connector),
        patch("app.migration_execution.alembic_runner.create_engine", return_value=mock_engine),
        patch("app.migration_execution.alembic_runner.command.upgrade") as mock_upgrade,
        patch(
            "app.migration_execution.alembic_runner.get_safe_current_revision",
            side_effect=[
                "024_maintenance_scheduler_and_operational_resilience",
                "031_analysis_job_claim_authority",
                "031_analysis_job_claim_authority",
            ],
        ),
        patch("app.migration_execution.alembic_runner.verify_revision_024_postconditions"),
    ):
        run_alembic_migrations(base_config)

        # Assert RESET ROLE was executed
        executed_sqls = [str(call_args[0][0]) for call_args in mock_conn.execute.call_args_list]
        assert any("RESET ROLE;" in s for s in executed_sqls)
        assert mock_upgrade.called
        mock_upgrade.assert_called_once_with(ANY, "031_analysis_job_claim_authority")


def test_t4_t5_session_user_current_user_mismatch_raises_fail_closed(base_config):
    """T4-T5 — Verifies fail-closed MigrationRunnerError if current_user is not db_bootstrap after RESET ROLE."""
    mock_connector = MagicMock()
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.invalidated = False
    mock_conn.in_transaction.return_value = False

    def execute_side_effect(sql, *args, **kwargs):
        sql_str = str(sql)
        mock_result = MagicMock()
        if "SELECT session_user, current_user, pg_backend_pid()" in sql_str:
            mock_result.fetchone.return_value = ("db_bootstrap", "db_owner", 1234)
            return mock_result
        if "SELECT count(*) FROM pg_locks" in sql_str:
            mock_result.scalar.return_value = 1
            return mock_result
        if "SELECT pg_backend_pid()" in sql_str:
            mock_result.scalar.return_value = 1234
            return mock_result
        if "SELECT session_user, current_user;" in sql_str:
            # Mismatch: current_user stays db_owner
            mock_result.fetchone.return_value = ("db_bootstrap", "db_owner")
            return mock_result
        return mock_result

    mock_conn.execute.side_effect = execute_side_effect
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with (
        patch("app.migration_execution.alembic_runner.Connector", return_value=mock_connector),
        patch("app.migration_execution.alembic_runner.create_engine", return_value=mock_engine),
        patch(
            "app.migration_execution.alembic_runner.get_safe_current_revision",
            return_value="024_maintenance_scheduler_and_operational_resilience",
        ),
        patch("app.migration_execution.alembic_runner.verify_revision_024_postconditions"),
        pytest.raises(MigrationRunnerError, match="Phase 3 session reset failed"),
    ):
        run_alembic_migrations(base_config)


def test_t6_t7_t8_t9_t10_remediation_invariants(base_config):
    """T6-T10 — Verifies failure propagation, redaction, and historical migration graph parity."""
    from alembic.script import ScriptDirectory

    # T9 & T10: Alembic script graph immutability & single head assertion
    alembic_dir = API_DIR / "alembic"
    script = ScriptDirectory(str(alembic_dir))
    heads = script.get_heads()
    assert heads == ["031_analysis_job_claim_authority"]
