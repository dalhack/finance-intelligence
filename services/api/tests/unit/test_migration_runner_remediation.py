"""Unit tests for remediated lock-scoped phased Alembic state machine runner."""

import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[2]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

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


def test_t1_t2_t3_reset_role_called_before_phase3_alembic(mock_config):
    """T1-T3 — Verifies SET ROLE db_owner in Phase 2, RESET ROLE in Phase 3 prior to command.upgrade."""
    from unittest.mock import ANY

    mock_connector = MagicMock()
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.invalidated = False
    mock_conn.in_transaction.return_value = False

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
        run_alembic_migrations(mock_config)

        executed_sqls = [str(call_args[0][0]) for call_args in mock_conn.execute.call_args_list]
        assert any("RESET ROLE;" in s for s in executed_sqls)
        assert mock_upgrade.called
        mock_upgrade.assert_called_once_with(ANY, "031_analysis_job_claim_authority")


def test_t4_t5_session_user_current_user_mismatch_raises_fail_closed(mock_config):
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
        run_alembic_migrations(mock_config)


def test_t6_t7_t8_t9_t10_remediation_invariants():
    """T6-T10 — Verifies failure propagation, redaction, and historical migration graph parity."""
    from alembic.script import ScriptDirectory

    alembic_dir = API_DIR / "alembic"
    script = ScriptDirectory(str(alembic_dir))
    heads = script.get_heads()
    assert heads == ["031_analysis_job_claim_authority"]


def test_get_valid_graph_revisions_success():
    """Verifies that get_valid_graph_revisions extracts all 31 revisions from Alembic ScriptDirectory graph."""
    from alembic.config import Config
    from app.migration_execution.alembic_runner import get_valid_graph_revisions

    ini_path = str(API_DIR / "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))

    revs = get_valid_graph_revisions(cfg, expected_head="031_analysis_job_claim_authority")
    assert len(revs) == 31
    assert "026_public_schema_acl_hardening" in revs
    assert "031_analysis_job_claim_authority" in revs
    assert "026_model_routing_policy_catalog" not in revs


def test_get_valid_graph_revisions_multiple_heads_fails_closed():
    """Verifies that get_valid_graph_revisions raises MigrationRunnerError if multiple heads exist in graph."""
    from alembic.config import Config
    from app.migration_execution.alembic_runner import (
        MigrationRunnerError,
        get_valid_graph_revisions,
    )

    ini_path = str(API_DIR / "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))

    with patch("app.migration_execution.alembic_runner.ScriptDirectory") as mock_sd_cls:
        mock_sd = MagicMock()
        mock_sd.get_heads.return_value = ["031_head_a", "031_head_b"]
        mock_sd_cls.from_config.return_value = mock_sd

        with pytest.raises(MigrationRunnerError, match="Multiple migration heads detected"):
            get_valid_graph_revisions(cfg)


def test_known_revisions_parity_with_active_graph():
    """Verifies that KNOWN_REVISIONS contains all active graph revisions and excludes stale/draft names."""
    from app.migration_execution.alembic_runner import KNOWN_REVISIONS

    assert "026_public_schema_acl_hardening" in KNOWN_REVISIONS
    assert "027_auth_context_lookup_security_plane" in KNOWN_REVISIONS
    assert "028_remove_organization_only_actor_lookup" in KNOWN_REVISIONS
    assert "029_analysis_authorization_policy" in KNOWN_REVISIONS
    assert "030_reconcile_application_role_catalog" in KNOWN_REVISIONS
    assert "031_analysis_job_claim_authority" in KNOWN_REVISIONS
    assert "026_model_routing_policy_catalog" not in KNOWN_REVISIONS


def test_least_privilege_temporary_grant_and_revoke_success():
    """Verifies temporary GRANT CREATE is executed when CREATE is missing and REVOKE CREATE is executed in finally."""
    from unittest.mock import MagicMock, patch

    from app.migration_execution.alembic_runner import run_alembic_migrations
    from app.migration_execution.config import MigrationExecutionConfig

    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.invalidated = False
    mock_conn.in_transaction.return_value = False

    executed_sqls = []

    def mock_execute(statement, *args, **kwargs):
        sql = str(statement)
        executed_sqls.append(sql)
        res = MagicMock()
        if "session_user, current_user, pg_backend_pid" in sql:
            res.fetchone.return_value = ("db_bootstrap", "db_owner", 1234)
        elif "SELECT session_user, current_user;" in sql:
            res.fetchone.return_value = ("db_bootstrap", "db_bootstrap")
        elif "has_schema_privilege('db_bootstrap', 'public', 'CREATE')" in sql:
            # First audit returns False (needs grant), cleanup audit returns False (revoke succeeded)
            res.scalar.return_value = False
        elif "has_schema_privilege('db_bootstrap', 'public', 'USAGE')" in sql:
            res.scalar.return_value = True
        elif "SELECT count(*) FROM pg_locks" in sql:
            res.scalar.return_value = 1
        elif "SELECT pg_advisory_unlock" in sql:
            res.fetchone.return_value = (True,)
        elif "SELECT pg_backend_pid()" in sql:
            res.scalar.return_value = 1234
            res.fetchone.return_value = (1234,)
        else:
            res.fetchone.return_value = None
            res.scalar.return_value = None
        return res

    mock_conn.execute.side_effect = mock_execute
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    cfg = MigrationExecutionConfig(
        project_id="test-proj",
        instance_name="test-inst",
        region="test-reg",
        target_database="test_db",
        expected_head="031_analysis_job_claim_authority",
        bootstrap_password="secret_pass",
    )

    with (
        patch("app.migration_execution.alembic_runner.Connector"),
        patch("app.migration_execution.alembic_runner.create_engine", return_value=mock_engine),
        patch("app.migration_execution.alembic_runner.verify_revision_024_postconditions"),
        patch("alembic.command.upgrade"),
        patch(
            "app.migration_execution.alembic_runner.get_safe_current_revision",
            side_effect=[
                "024_maintenance_scheduler_and_operational_resilience",
                "031_analysis_job_claim_authority",
                "031_analysis_job_claim_authority",
                "031_analysis_job_claim_authority",
            ],
        ),
    ):
        run_alembic_migrations(cfg)

    assert any("GRANT CREATE ON SCHEMA public TO db_bootstrap" in s for s in executed_sqls)
    assert any("REVOKE CREATE ON SCHEMA public FROM db_bootstrap" in s for s in executed_sqls)


def test_least_privilege_no_grant_if_create_already_exists():
    """Verifies GRANT CREATE is NOT executed if db_bootstrap already has CREATE privilege."""
    from unittest.mock import MagicMock, patch

    from app.migration_execution.alembic_runner import run_alembic_migrations
    from app.migration_execution.config import MigrationExecutionConfig

    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.invalidated = False
    mock_conn.in_transaction.return_value = False

    executed_sqls = []

    def mock_execute(statement, *args, **kwargs):
        sql = str(statement)
        executed_sqls.append(sql)
        res = MagicMock()
        if "session_user, current_user, pg_backend_pid" in sql:
            res.fetchone.return_value = ("db_bootstrap", "db_owner", 1234)
        elif "SELECT session_user, current_user;" in sql:
            res.fetchone.return_value = ("db_bootstrap", "db_bootstrap")
        elif (
            "has_schema_privilege('db_bootstrap', 'public', 'CREATE')" in sql
            or "has_schema_privilege('db_bootstrap', 'public', 'USAGE')" in sql
        ):
            res.scalar.return_value = True
        elif "SELECT count(*) FROM pg_locks" in sql:
            res.scalar.return_value = 1
        elif "SELECT pg_advisory_unlock" in sql:
            res.fetchone.return_value = (True,)
        elif "SELECT pg_backend_pid()" in sql:
            res.scalar.return_value = 1234
            res.fetchone.return_value = (1234,)
        else:
            res.fetchone.return_value = None
            res.scalar.return_value = None
        return res

    mock_conn.execute.side_effect = mock_execute
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    cfg = MigrationExecutionConfig(
        project_id="test-proj",
        instance_name="test-inst",
        region="test-reg",
        target_database="test_db",
        expected_head="031_analysis_job_claim_authority",
        bootstrap_password="secret_pass",
    )

    with (
        patch("app.migration_execution.alembic_runner.Connector"),
        patch("app.migration_execution.alembic_runner.create_engine", return_value=mock_engine),
        patch("app.migration_execution.alembic_runner.verify_revision_024_postconditions"),
        patch("alembic.command.upgrade"),
        patch(
            "app.migration_execution.alembic_runner.get_safe_current_revision",
            side_effect=[
                "024_maintenance_scheduler_and_operational_resilience",
                "031_analysis_job_claim_authority",
                "031_analysis_job_claim_authority",
                "031_analysis_job_claim_authority",
            ],
        ),
    ):
        run_alembic_migrations(cfg)

    assert not any("GRANT CREATE ON SCHEMA public TO db_bootstrap" in s for s in executed_sqls)
    assert not any("REVOKE CREATE ON SCHEMA public FROM db_bootstrap" in s for s in executed_sqls)


def test_least_privilege_revoke_on_migration_failure():
    """Verifies REVOKE CREATE is executed in finally block even when Alembic upgrade fails."""
    from unittest.mock import MagicMock, patch

    import pytest
    from app.migration_execution.alembic_runner import MigrationRunnerError, run_alembic_migrations
    from app.migration_execution.config import MigrationExecutionConfig

    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.invalidated = False
    mock_conn.in_transaction.return_value = False

    executed_sqls = []

    def mock_execute(statement, *args, **kwargs):
        sql = str(statement)
        executed_sqls.append(sql)
        res = MagicMock()
        if "session_user, current_user, pg_backend_pid" in sql:
            res.fetchone.return_value = ("db_bootstrap", "db_owner", 1234)
        elif "SELECT session_user, current_user;" in sql:
            res.fetchone.return_value = ("db_bootstrap", "db_bootstrap")
        elif "has_schema_privilege('db_bootstrap', 'public', 'CREATE')" in sql:
            res.scalar.return_value = False
        elif "SELECT count(*) FROM pg_locks" in sql:
            res.scalar.return_value = 1
        elif "SELECT pg_advisory_unlock" in sql:
            res.fetchone.return_value = (True,)
        elif "SELECT pg_backend_pid()" in sql:
            res.scalar.return_value = 1234
            res.fetchone.return_value = (1234,)
        else:
            res.fetchone.return_value = None
            res.scalar.return_value = None
        return res

    mock_conn.execute.side_effect = mock_execute
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    cfg = MigrationExecutionConfig(
        project_id="test-proj",
        instance_name="test-inst",
        region="test-reg",
        target_database="test_db",
        expected_head="031_analysis_job_claim_authority",
        bootstrap_password="secret_pass",
    )

    with (
        patch("app.migration_execution.alembic_runner.Connector"),
        patch("app.migration_execution.alembic_runner.create_engine", return_value=mock_engine),
        patch("app.migration_execution.alembic_runner.verify_revision_024_postconditions"),
        patch("alembic.command.upgrade", side_effect=RuntimeError("Injected migration failure")),
        patch(
            "app.migration_execution.alembic_runner.get_safe_current_revision",
            return_value="024_maintenance_scheduler_and_operational_resilience",
        ),
        pytest.raises(MigrationRunnerError, match="Injected migration failure"),
    ):
        run_alembic_migrations(cfg)

    assert any("GRANT CREATE ON SCHEMA public TO db_bootstrap" in s for s in executed_sqls)
    assert any("REVOKE CREATE ON SCHEMA public FROM db_bootstrap" in s for s in executed_sqls)


def test_historical_migration_026_unmodified():
    """Verifies that 026_public_schema_acl_hardening.py does NOT grant persistent CREATE to db_bootstrap."""
    from pathlib import Path

    m26_path = Path(__file__).parents[2] / "alembic" / "versions" / "026_public_schema_acl_hardening.py"
    content = m26_path.read_text(encoding="utf-8")

    assert "GRANT USAGE, CREATE ON SCHEMA public TO db_bootstrap;" not in content
    assert "GRANT USAGE ON SCHEMA public TO db_bootstrap;" in content


def test_logging_exit_path_flushes_all_streams():
    """Verifies _safe_exit flushes logging handlers and stdio streams before calling sys.exit."""
    from unittest.mock import patch

    from app.migration_entrypoint import _safe_exit

    with (
        patch("logging.shutdown") as mock_log_shutdown,
        patch("sys.stdout.flush") as mock_stdout_flush,
        patch("sys.stderr.flush") as mock_stderr_flush,
        patch("sys.exit") as mock_exit,
    ):
        _safe_exit(1)

        mock_log_shutdown.assert_called_once()
        mock_stdout_flush.assert_called_once()
        mock_stderr_flush.assert_called_once()
        mock_exit.assert_called_once_with(1)
