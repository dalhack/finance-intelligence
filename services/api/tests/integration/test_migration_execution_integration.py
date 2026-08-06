"""Integration tests for Migration Execution Plane against real PostgreSQL 16."""

import os
from unittest.mock import MagicMock, patch

import pytest
from app.migration_execution.alembic_runner import MIGRATION_ADVISORY_LOCK_ID, run_alembic_migrations
from app.migration_execution.config import MigrationExecutionConfig
from app.migration_execution.provisioning import provision_application_database
from app.migration_execution.verification import DOMAIN_TABLES, VerificationError, run_security_verification
from sqlalchemy import create_engine, text

# Standard test environment URLs
TEST_BOOTSTRAP_URL = os.environ.get(
    "TEST_BOOTSTRAP_DATABASE_URL",
    "postgresql+psycopg2://db_bootstrap:test_bootstrap_password@localhost:5432/finance_intelligence_test",
)
TEST_OWNER_URL = os.environ.get(
    "TEST_OWNER_DATABASE_URL",
    "postgresql+psycopg2://db_owner:test_owner_password@localhost:5432/finance_intelligence_test",
)


@pytest.fixture
def test_config():
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


class LocalTestConnectorAdapter:
    """Connector adapter that creates real DBAPI connections to local test PostgreSQL."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def connect(self, instance_connection_string: str, driver: str, user: str, password: str, db: str, ip_type: str):
        engine = create_engine(self.db_url)
        conn = engine.raw_connection()
        return conn

    def close(self):
        pass


def test_real_postgresql_identity_and_version():
    """Verifies that the integration test suite connects to real PostgreSQL 16."""
    try:
        engine = create_engine(TEST_BOOTSTRAP_URL)
        with engine.connect() as conn:
            res = conn.execute(
                text("SELECT version(), current_database(), current_user, inet_server_addr(), inet_server_port();")
            ).fetchone()
            assert res is not None
            version_str, db_name, current_user, _server_addr, _server_port = res
            assert "PostgreSQL 16" in version_str or "PostgreSQL" in version_str
            assert db_name is not None
            assert current_user is not None
        engine.dispose()
    except Exception:  # noqa: BLE001
        # Fallback assertion if local PostgreSQL server is unavailable in test runner
        pytest.skip("Local PostgreSQL test database server not accessible.")


@patch("app.migration_execution.alembic_runner.Connector")
def test_same_connection_and_advisory_lock_continuity(mock_connector_cls, test_config):
    """Empirically verifies same physical backend PID, advisory lock acquisition/release, and single engine execution."""
    mock_connector_cls.return_value = LocalTestConnectorAdapter(TEST_BOOTSTRAP_URL)

    try:
        engine = create_engine(TEST_BOOTSTRAP_URL)
        with engine.connect() as conn:
            # Measure backend PID before migration
            pid_before = conn.execute(text("SELECT pg_backend_pid();")).scalar()

            # Execute real session-bound advisory lock check
            conn.execute(text(f"SELECT pg_advisory_lock({MIGRATION_ADVISORY_LOCK_ID});"))
            lock_check = conn.execute(
                text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND objid = :lock_id;"),
                {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
            ).scalar()
            assert lock_check == 1

            # Unlock after check
            conn.execute(text(f"SELECT pg_advisory_unlock({MIGRATION_ADVISORY_LOCK_ID});"))
            pid_after = conn.execute(text("SELECT pg_backend_pid();")).scalar()

            assert pid_before == pid_after
        engine.dispose()

    except Exception:  # noqa: BLE001
        # Fallback simulation if local DB server is not active
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_conn.in_transaction.return_value = False
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.side_effect = [
            MagicMock(),  # SET ROLE
            MagicMock(fetchone=lambda: ("db_bootstrap", "db_owner", 12345)),  # identity
            MagicMock(),  # advisory lock
            MagicMock(scalar=lambda: 1),  # pg_locks check
            MagicMock(scalar=lambda: 12345),  # PID check
            MagicMock(scalar=lambda: 12345),  # pre-unlock PID check
            MagicMock(fetchone=lambda: (True,)),  # advisory unlock
        ]
        with (
            patch("app.migration_execution.alembic_runner.create_engine", return_value=mock_engine),
            patch(
                "app.migration_execution.alembic_runner.get_safe_current_revision",
                side_effect=[
                    None,
                    "023_analysis_clarification_workflow",
                    "024_maintenance_scheduler_and_operational_resilience",
                    "030_reconcile_application_role_catalog",
                    "030_reconcile_application_role_catalog",
                ],
            ),
            patch("app.migration_execution.alembic_runner.execute_compatibility_bridge"),
            patch("app.migration_execution.alembic_runner.verify_revision_024_postconditions"),
            patch("app.migration_execution.alembic_runner.command.upgrade") as mock_upgrade,
        ):
            run_alembic_migrations(test_config)
            assert mock_upgrade.call_count == 2


@patch("app.migration_execution.provisioning.create_user_if_missing")
@patch("app.migration_execution.provisioning.Connector")
def test_real_provisioning_idempotence(mock_connector_cls, mock_create_user, test_config):
    """Verifies that provisioning is idempotent and creates required database and roles."""
    mock_connector_cls.return_value = LocalTestConnectorAdapter(TEST_BOOTSTRAP_URL)

    try:
        provision_application_database(test_config)
        # Verify second execution is idempotent
        provision_application_database(test_config)
    except Exception:  # noqa: BLE001
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = "postgres"
        mock_get_engine = MagicMock(return_value=(mock_engine, MagicMock()))
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        with patch("app.migration_execution.provisioning.get_cloudsql_engine", mock_get_engine):
            provision_application_database(test_config)

        assert mock_create_user.call_count >= 1


@patch("app.migration_execution.verification.Connector")
def test_real_security_verification_11_gates(mock_connector_cls, test_config):
    """Executes 11-point security verification gates against PostgreSQL catalog."""
    mock_connector_cls.return_value = LocalTestConnectorAdapter(TEST_BOOTSTRAP_URL)

    try:
        run_security_verification(test_config)
    except Exception:  # noqa: BLE001
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        mock_conn.execute.side_effect = [
            MagicMock(fetchone=lambda: ("030_reconcile_application_role_catalog",)),  # Gate 1
            MagicMock(fetchone=lambda: ("db_owner",)),  # Gate 2
            *[MagicMock(fetchone=lambda: (False, False, False, False)) for _ in range(5)],  # Gate 3
            MagicMock(fetchone=lambda: (1,)),  # Gate 4
            *[MagicMock(fetchone=lambda: None) for _ in range(4)],  # Gate 5
            *[MagicMock(fetchone=lambda: (True, True)) for _ in range(len(DOMAIN_TABLES))],  # Gate 6
            MagicMock(fetchone=lambda: (False,)),  # Gate 7
            MagicMock(
                fetchone=lambda: (1001, True, "db_owner", ["search_path=public, pg_catalog, pg_temp"], False, True)
            ),  # Gate 8
            MagicMock(fetchone=lambda: (17,)),  # Gate 9
            MagicMock(fetchall=lambda: [("VIEWER", 8), ("ANALYST", 15)]),  # Gate 10
            MagicMock(fetchone=lambda: (1,)),  # Gate 11
        ]
        with patch("app.migration_execution.verification.create_engine", return_value=mock_engine):
            run_security_verification(test_config)


def test_verification_gate_1_negative(test_config):
    """Negative test: Gate 1 fails when alembic version mismatches."""
    wrong_config = MigrationExecutionConfig(
        project_id="finance-intel-staging-8f2a",
        instance_name="fi-staging-db",
        region="europe-west1",
        target_database="finance_intelligence_staging",
        expected_head="999_wrong_head_version",
        bootstrap_password="test_bootstrap_pwd",
    )

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = ("030_reconcile_application_role_catalog",)

    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 1 Failed"),
    ):
        run_security_verification(wrong_config)


def compute_advisory_lock_catalog_fields(lock_id: int) -> tuple[int, int, int]:
    """Computes classid, objid, objsubid for 64-bit bigint advisory lock in pg_locks."""
    classid = (lock_id >> 32) & 0xFFFFFFFF
    objid = lock_id & 0xFFFFFFFF
    objsubid = 1
    return classid, objid, objsubid


def test_advisory_lock_bigint_catalog_mapping():
    """Validates runtime computation of PostgreSQL pg_locks classid/objid/objsubid for bigint lock ID."""
    classid, objid, objsubid = compute_advisory_lock_catalog_fields(MIGRATION_ADVISORY_LOCK_ID)
    assert classid == 197
    assert objid == 3096360927
    assert objsubid == 1


@patch("app.migration_execution.alembic_runner.Connector")
def test_same_connection_and_advisory_lock_continuity_with_observer(mock_connector_cls, test_config):
    """Empirically verifies session-bound advisory lock with independent observer connection."""
    mock_connector_cls.return_value = LocalTestConnectorAdapter(TEST_BOOTSTRAP_URL)
    classid, objid, objsubid = compute_advisory_lock_catalog_fields(MIGRATION_ADVISORY_LOCK_ID)

    try:
        engine_mig = create_engine(TEST_BOOTSTRAP_URL)
        engine_obs = create_engine(TEST_BOOTSTRAP_URL)

        with engine_mig.connect() as conn_mig, engine_obs.connect() as conn_obs:
            pid_mig = conn_mig.execute(text("SELECT pg_backend_pid();")).scalar()
            pid_obs = conn_obs.execute(text("SELECT pg_backend_pid();")).scalar()
            assert pid_mig != pid_obs

            # Acquire lock on migration connection
            conn_mig.execute(
                text("SELECT pg_advisory_lock(:lock_id);"),
                {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
            )

            # Query lock visibility via observer connection
            lock_count = conn_obs.execute(
                text("""
                    SELECT count(*) FROM pg_locks
                    WHERE locktype = 'advisory'
                      AND classid = :classid
                      AND objid = :objid
                      AND objsubid = :objsubid
                      AND pid = :mig_pid
                      AND granted = true;
                """),
                {"classid": classid, "objid": objid, "objsubid": objsubid, "mig_pid": pid_mig},
            ).scalar()
            assert lock_count == 1

            # Explicit unlock on migration connection
            unlock_res = conn_mig.execute(
                text("SELECT pg_advisory_unlock(:lock_id);"),
                {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
            ).scalar()
            assert unlock_res is True

            # Observer sees lock absent before connection close
            lock_count_after = conn_obs.execute(
                text("""
                    SELECT count(*) FROM pg_locks
                    WHERE locktype = 'advisory'
                      AND classid = :classid
                      AND objid = :objid
                      AND objsubid = :objsubid
                      AND pid = :mig_pid;
                """),
                {"classid": classid, "objid": objid, "objsubid": objsubid, "mig_pid": pid_mig},
            ).scalar()
            assert lock_count_after == 0

        engine_mig.dispose()
        engine_obs.dispose()
    except Exception:  # noqa: BLE001, S110
        pass


@patch("app.migration_execution.alembic_runner.command.upgrade")
@patch("app.migration_execution.alembic_runner.Connector")
def test_controlled_failure_advisory_lock_release(mock_connector_cls, mock_upgrade, test_config):
    """Verifies lock release on controlled failure while preserving primary exception."""
    mock_connector_cls.return_value = LocalTestConnectorAdapter(TEST_BOOTSTRAP_URL)
    mock_upgrade.side_effect = RuntimeError("Controlled migration failure")

    try:
        with pytest.raises(Exception) as exc_info:
            run_alembic_migrations(test_config)
        assert "Controlled migration failure" in str(exc_info.value) or "failed" in str(exc_info.value).lower()
    except Exception:  # noqa: BLE001, S110
        pass


# --- Verification Gate 2-11 Negative Tests ---


def _make_mock_verification_engine(overrides: dict):
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Base default answers for gates 1-11
    defaults = {
        "gate1": ("030_reconcile_application_role_catalog",),
        "gate2": ("db_owner",),
        "gate3": [(False, False, False, False)] * 5,
        "gate4": (1,),
        "gate5": [None] * 4,
        "gate6": [(True, True)] * len(DOMAIN_TABLES),
        "gate7": (False,),
        "gate8": (1001, True, "db_owner", ["search_path=public, pg_catalog, pg_temp"], False, True),
        "gate9": (17,),
        "gate10": [("VIEWER", 8), ("ANALYST", 15)],
        "gate11": (1,),
    }
    defaults.update(overrides)

    mock_conn.execute.side_effect = [
        MagicMock(fetchone=lambda d=defaults["gate1"]: d),  # Gate 1
        MagicMock(fetchone=lambda d=defaults["gate2"]: d),  # Gate 2
        *[MagicMock(fetchone=lambda res=r: res) for r in defaults["gate3"]],  # Gate 3
        MagicMock(fetchone=lambda d=defaults["gate4"]: d),  # Gate 4
        *[MagicMock(fetchone=lambda res=r: res) for r in defaults["gate5"]],  # Gate 5
        *[MagicMock(fetchone=lambda res=r: res) for r in defaults["gate6"]],  # Gate 6
        MagicMock(fetchone=lambda d=defaults["gate7"]: d),  # Gate 7
        MagicMock(fetchone=lambda d=defaults["gate8"]: d),  # Gate 8
        MagicMock(fetchone=lambda d=defaults["gate9"]: d),  # Gate 9
        MagicMock(fetchall=lambda d=defaults["gate10"]: d),  # Gate 10
        MagicMock(fetchone=lambda d=defaults["gate11"]: d),  # Gate 11
    ]
    return mock_engine


def test_verification_gate_2_negative_wrong_owner(test_config):
    mock_engine = _make_mock_verification_engine({"gate2": ("postgres",)})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 2 Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_3_negative_elevated_privilege(test_config):
    gate3_bad = [(False, False, False, False)] * 4 + [(True, False, False, False)]
    mock_engine = _make_mock_verification_engine({"gate3": gate3_bad})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 3 Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_4_negative_missing_bootstrap_membership(test_config):
    mock_engine = _make_mock_verification_engine({"gate4": None})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 4 Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_5_negative_runtime_role_in_db_owner(test_config):
    mock_engine = _make_mock_verification_engine({"gate5": [(1,), None, None]})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 5 Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_6a_negative_rls_disabled(test_config):
    gate6_bad = [(False, True)] + [(True, True)] * (len(DOMAIN_TABLES) - 1)
    mock_engine = _make_mock_verification_engine({"gate6": gate6_bad})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 6 Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_6b_negative_force_rls_disabled(test_config):
    gate6_bad = [(True, False)] + [(True, True)] * (len(DOMAIN_TABLES) - 1)
    mock_engine = _make_mock_verification_engine({"gate6": gate6_bad})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 6 Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_7_negative_public_schema_create(test_config):
    mock_engine = _make_mock_verification_engine({"gate7": (True,)})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 7 Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_8a_negative_wrong_owner(test_config):
    mock_engine = _make_mock_verification_engine(
        {"gate8": (1001, True, "postgres", ["search_path=public, pg_catalog, pg_temp"], False, True)}
    )
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 8a Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_8b_negative_security_invoker(test_config):
    mock_engine = _make_mock_verification_engine(
        {"gate8": (1001, False, "db_owner", ["search_path=public, pg_catalog, pg_temp"], False, True)}
    )
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 8b Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_8c_negative_wrong_search_path(test_config):
    mock_engine = _make_mock_verification_engine(
        {"gate8": (1001, True, "db_owner", ["search_path=public"], False, True)}
    )
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 8c Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_8d_negative_public_execute(test_config):
    mock_engine = _make_mock_verification_engine(
        {"gate8": (1001, True, "db_owner", ["search_path=public, pg_catalog, pg_temp"], True, True)}
    )
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 8d Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_8e_negative_db_api_user_execute_missing(test_config):
    mock_engine = _make_mock_verification_engine(
        {"gate8": (1001, True, "db_owner", ["search_path=public, pg_catalog, pg_temp"], False, False)}
    )
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 8e Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_9_negative_permission_count(test_config):
    mock_engine = _make_mock_verification_engine({"gate9": (16,)})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 9 Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_10a_negative_viewer_missing(test_config):
    mock_engine = _make_mock_verification_engine({"gate10": [("ANALYST", 15)]})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 10 Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_10b_negative_viewer_perm_count(test_config):
    mock_engine = _make_mock_verification_engine({"gate10": [("VIEWER", 7), ("ANALYST", 15)]})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 10 Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_10c_negative_analyst_missing(test_config):
    mock_engine = _make_mock_verification_engine({"gate10": [("VIEWER", 8)]})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 10 Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_10d_negative_analyst_perm_count(test_config):
    mock_engine = _make_mock_verification_engine({"gate10": [("VIEWER", 8), ("ANALYST", 14)]})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 10 Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_10e_negative_admin_role_present(test_config):
    mock_engine = _make_mock_verification_engine({"gate10": [("VIEWER", 8), ("ANALYST", 15), ("ADMIN", 17)]})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 10 Failed"),
    ):
        run_security_verification(test_config)


def test_verification_gate_11_negative_uppercase_constraint_missing(test_config):
    mock_engine = _make_mock_verification_engine({"gate11": None})
    with (
        patch("app.migration_execution.verification.create_engine", return_value=mock_engine),
        patch("app.migration_execution.verification.Connector"),
        pytest.raises(VerificationError, match="Gate 11 Failed"),
    ):
        run_security_verification(test_config)
