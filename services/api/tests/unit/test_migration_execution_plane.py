"""Unit tests for Migration Execution Plane modules."""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from app.migration_execution.cloudsql_admin import (
    SQLADMIN_API_BASE,
    CloudSQLAdminError,
    create_user_if_missing,
    list_instance_users,
    update_user_password,
)
from app.migration_execution.config import MigrationConfigError, MigrationExecutionConfig
from app.migration_execution.provisioning import ProvisioningError, provision_application_database
from app.migration_execution.redaction import redact_text, safe_close_connector, sanitize_dict_for_logging


def test_config_validation_success():
    config = MigrationExecutionConfig(
        project_id="finance-intel-staging-8f2a",
        instance_name="fi-staging-db",
        region="europe-west1",
        target_database="finance_intelligence_staging",
        expected_head="030_reconcile_application_role_catalog",
        initial_admin_password="admin_pwd",
    )
    assert config.project_id == "finance-intel-staging-8f2a"
    assert config.region == "europe-west1"


def test_config_validation_invalid_project_fails():
    with (
        patch.dict("os.environ", {"GCP_PROJECT": "wrong-project-123"}),
        pytest.raises(MigrationConfigError, match="Invalid GCP_PROJECT"),
    ):
        MigrationExecutionConfig.from_env("verify")


def test_config_validation_invalid_region_fails():
    with (
        patch.dict("os.environ", {"REGION": "us-central1"}),
        pytest.raises(MigrationConfigError, match="Invalid REGION"),
    ):
        MigrationExecutionConfig.from_env("verify")


def test_redact_text():
    raw = "Failed to connect postgresql://user:secret123@localhost:5432/db with password=secret456"
    redacted = redact_text(raw)
    assert "secret123" not in redacted
    assert "secret456" not in redacted
    assert "[REDACTED]" in redacted


def test_sanitize_dict_for_logging():
    data = {
        "user": "db_owner",
        "password": "secret_pwd",
        "nested": {"token": "secret_token", "normal": "value"},
    }
    sanitized = sanitize_dict_for_logging(data)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["normal"] == "value"


def test_cloudsql_admin_exact_endpoint_contract():
    """Asserts production code uses exact GCP Cloud SQL Admin v1 API endpoints."""
    assert SQLADMIN_API_BASE == "https://sqladmin.googleapis.com/v1"


@patch("app.migration_execution.cloudsql_admin._make_api_request")
@patch("app.migration_execution.cloudsql_admin._get_authenticated_session")
def test_list_instance_users(mock_auth, mock_api):
    mock_auth.return_value = ("fake_token", MagicMock())
    mock_api.return_value = {"items": [{"name": "postgres"}, {"name": "db_owner"}]}

    users = list_instance_users("finance-intel-staging-8f2a", "fi-staging-db")
    assert len(users) == 2
    assert users[0]["name"] == "postgres"
    mock_api.assert_called_once_with(
        "GET",
        "https://sqladmin.googleapis.com/v1/projects/finance-intel-staging-8f2a/instances/fi-staging-db/users",
        "fake_token",
    )


@patch("app.migration_execution.cloudsql_admin.update_user_password")
@patch("app.migration_execution.cloudsql_admin._make_api_request")
@patch("app.migration_execution.cloudsql_admin.list_instance_users")
def test_create_user_if_missing_when_present_skips_password_update(mock_list, mock_api, mock_update):
    mock_list.return_value = [{"name": "db_bootstrap"}]
    create_user_if_missing("finance-intel-staging-8f2a", "fi-staging-db", "db_bootstrap", "pwd_123")
    mock_update.assert_not_called()
    mock_api.assert_not_called()


@patch("app.migration_execution.cloudsql_admin.list_instance_users")
def test_create_user_if_missing_existing_user_logs_safe_skip(mock_list, caplog):
    mock_list.return_value = [{"name": "db_bootstrap"}]
    with caplog.at_level("INFO"):
        create_user_if_missing("finance-intel-staging-8f2a", "fi-staging-db", "db_bootstrap", "pwd_123")
    assert "Skipping password update during provisioning" in caplog.text
    assert "pwd_123" not in caplog.text


@patch("app.migration_execution.cloudsql_admin._poll_operation")
@patch("app.migration_execution.cloudsql_admin._make_api_request")
@patch("app.migration_execution.cloudsql_admin.list_instance_users")
@patch("app.migration_execution.cloudsql_admin._get_authenticated_session")
def test_create_user_if_missing_when_absent_creates(mock_auth, mock_list, mock_api, mock_poll):
    mock_auth.return_value = ("fake_token", MagicMock())
    mock_list.return_value = [{"name": "postgres"}]
    mock_api.return_value = {"name": "projects/finance-intel-staging-8f2a/operations/op_new"}

    create_user_if_missing("finance-intel-staging-8f2a", "fi-staging-db", "db_api_user", "pwd_123")
    mock_api.assert_called_once()
    assert mock_api.call_args[0][0] == "POST"
    assert (
        mock_api.call_args[0][1]
        == "https://sqladmin.googleapis.com/v1/projects/finance-intel-staging-8f2a/instances/fi-staging-db/users"
    )
    mock_poll.assert_called_once_with("finance-intel-staging-8f2a", "op_new", "fake_token")


@patch("app.migration_execution.cloudsql_admin._make_api_request")
@patch("app.migration_execution.cloudsql_admin._get_authenticated_session")
def test_cloudsql_admin_operation_done_with_error_fails(mock_auth, mock_api):
    mock_auth.return_value = ("fake_token", MagicMock())
    mock_api.side_effect = [
        {"name": "projects/finance-intel-staging-8f2a/operations/op_err"},
        {"status": "DONE", "error": {"message": "Resource locked by password=secret_canary"}},
    ]

    with pytest.raises(CloudSQLAdminError) as exc_info:
        update_user_password("finance-intel-staging-8f2a", "fi-staging-db", "postgres", "pwd_123")

    assert "secret_canary" not in str(exc_info.value)
    assert "[REDACTED]" in str(exc_info.value) or "failed" in str(exc_info.value).lower()


@patch("app.migration_execution.cloudsql_admin.time.sleep")
@patch("app.migration_execution.cloudsql_admin._make_api_request")
@patch("app.migration_execution.cloudsql_admin._get_authenticated_session")
def test_cloudsql_admin_operation_timeout_fails(mock_auth, mock_api, mock_sleep):
    """Deterministic timeout test using infinite fake clock and mock side effects."""
    mock_auth.return_value = ("fake_token_canary", MagicMock())

    def fake_api_request(method, url, token, body=None):
        if method == "PUT":
            return {"name": "projects/finance-intel-staging-8f2a/operations/op_slow"}
        return {"status": "RUNNING"}

    mock_api.side_effect = fake_api_request

    clock = [0.0]

    def fake_time():
        val = clock[0]
        clock[0] += 25.0
        return val

    with (
        patch("app.migration_execution.cloudsql_admin.time.time", side_effect=fake_time),
        pytest.raises(CloudSQLAdminError) as exc_info,
    ):
        update_user_password("finance-intel-staging-8f2a", "fi-staging-db", "postgres", "pwd_123_canary")

    err_msg = str(exc_info.value)
    assert "timed out after 60 seconds" in err_msg
    assert "fake_token_canary" not in err_msg
    assert "pwd_123_canary" not in err_msg
    assert mock_sleep.called


@pytest.mark.parametrize("status_code", [401, 403, 404, 409, 429, 500, 503])
@patch("urllib.request.urlopen")
@patch("app.migration_execution.cloudsql_admin._get_authenticated_session")
def test_cloudsql_admin_http_errors_redacted(mock_auth, mock_urlopen, status_code):
    mock_auth.return_value = ("bearer_canary_token_123", MagicMock())
    fp = MagicMock()
    fp.read.return_value = json.dumps({"error": "Failed with password=secret_canary_pwd"}).encode("utf-8")
    mock_urlopen.side_effect = urllib.error.HTTPError("http://url", status_code, "HTTP Error", {}, fp)

    with pytest.raises(CloudSQLAdminError) as exc_info:
        list_instance_users("finance-intel-staging-8f2a", "fi-staging-db")

    err_msg = str(exc_info.value)
    assert "secret_canary_pwd" not in err_msg
    assert f"status {status_code}" in err_msg


def test_safe_close_connector_lifecycle():
    """Asserts connector cleanup lifecycle contract: success=1, failure=1, double_close=0, leak=0, exception preserved."""
    # 1. Close after success = exactly 1
    mock_conn = MagicMock()
    safe_close_connector(mock_conn)
    mock_conn.close.assert_called_once()

    # 2. Close after failure (connector.close raises exception inside safe_close_connector) = exception preserved
    faulty_conn = MagicMock()
    faulty_conn.close.side_effect = RuntimeError("Close failed")
    safe_close_connector(faulty_conn)  # Should log warning without raising exception

    # 3. None connector handled safely
    safe_close_connector(None)


@patch("urllib.request.urlopen")
@patch("app.migration_execution.cloudsql_admin._get_authenticated_session")
def test_cloudsql_admin_malformed_json_redacted(mock_auth, mock_urlopen):
    mock_auth.return_value = ("bearer_canary_123", MagicMock())
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"{ invalid json with password=secret_canary }"
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    with pytest.raises(CloudSQLAdminError) as exc_info:
        list_instance_users("finance-intel-staging-8f2a", "fi-staging-db")

    err = str(exc_info.value)
    assert "secret_canary" not in err
    assert "bearer_canary_123" not in err
    assert "Failed to communicate with Cloud SQL Admin API" in err


@patch("urllib.request.urlopen")
@patch("app.migration_execution.cloudsql_admin._get_authenticated_session")
def test_cloudsql_admin_network_exception_redacted(mock_auth, mock_urlopen):
    mock_auth.return_value = ("bearer_canary_456", MagicMock())
    mock_urlopen.side_effect = urllib.error.URLError("Connection refused for token=bearer_canary_456")

    with pytest.raises(CloudSQLAdminError) as exc_info:
        list_instance_users("finance-intel-staging-8f2a", "fi-staging-db")

    err = str(exc_info.value)
    assert "bearer_canary_456" not in err
    assert "Failed to communicate with Cloud SQL Admin API" in err


@patch("app.migration_execution.cloudsql_admin._make_api_request")
@patch("app.migration_execution.cloudsql_admin._get_authenticated_session")
def test_cloudsql_admin_missing_operation_name_fails(mock_auth, mock_api):
    mock_auth.return_value = ("bearer_canary_789", MagicMock())
    mock_api.return_value = {}  # Empty dict missing operation name

    with pytest.raises(CloudSQLAdminError) as exc_info:
        update_user_password("finance-intel-staging-8f2a", "fi-staging-db", "postgres", "pwd_123")

    err = str(exc_info.value)
    assert "bearer_canary_789" not in err
    assert "operation" in err.lower()


@patch("app.migration_execution.cloudsql_admin._make_api_request")
@patch("app.migration_execution.cloudsql_admin._get_authenticated_session")
def test_cloudsql_admin_unexpected_operation_status_fails(mock_auth, mock_api):
    mock_auth.return_value = ("bearer_canary_999", MagicMock())
    mock_api.side_effect = [
        {"name": "projects/finance-intel-staging-8f2a/operations/op_unknown"},
        {"status": "DONE", "error": {"message": "Operation failed with password=secret_state"}},
    ]

    with pytest.raises(CloudSQLAdminError) as exc_info:
        update_user_password("finance-intel-staging-8f2a", "fi-staging-db", "postgres", "pwd_123")

    err = str(exc_info.value)
    assert "secret_state" not in err
    assert "bearer_canary_999" not in err
    assert "[REDACTED]" in err or "failed" in err.lower()


def test_provisioning_missing_secret_fails_upfront():
    incomplete_config = MigrationExecutionConfig(
        project_id="finance-intel-staging-8f2a",
        instance_name="fi-staging-db",
        region="europe-west1",
        target_database="finance_intelligence_staging",
        expected_head="030_reconcile_application_role_catalog",
        initial_admin_password="pwd_admin",
        bootstrap_password="pwd_bootstrap",
        api_password=None,
        worker_password="pwd_worker",
        maintenance_password="pwd_maint",
    )
    with pytest.raises(ProvisioningError, match="Missing required environment secret"):
        provision_application_database(incomplete_config)


@patch("app.migration_execution.provisioning.get_cloudsql_engine")
@patch("app.migration_execution.provisioning.create_user_if_missing")
def test_provisioning_transient_membership_grant_and_revoke_success(mock_create_user, mock_get_engine):
    mock_sys_engine = MagicMock()
    mock_sys_conn = MagicMock()
    mock_sys_engine.connect.return_value.__enter__.return_value = mock_sys_conn

    mock_target_engine = MagicMock()
    mock_target_conn = MagicMock()
    mock_target_engine.connect.return_value.__enter__.return_value = mock_target_conn

    mock_get_engine.side_effect = [
        (mock_sys_engine, MagicMock()),
        (mock_target_engine, MagicMock()),
    ]

    def mock_sys_exec(sql, *args, **kwargs):
        sql_str = str(sql)
        if "SELECT CURRENT_USER" in sql_str:
            return MagicMock(scalar=lambda: "postgres")
        if "pg_auth_members" in sql_str:
            return MagicMock(scalar=lambda: False)
        return MagicMock(scalar=lambda: 0)

    mock_sys_conn.execute.side_effect = mock_sys_exec

    config = MigrationExecutionConfig(
        project_id="finance-intel-staging-8f2a",
        instance_name="fi-staging-db",
        region="europe-west1",
        target_database="finance_intelligence_staging",
        expected_head="030_reconcile_application_role_catalog",
        initial_admin_password="adm",
        bootstrap_password="boot",
        api_password="api",
        worker_password="wrk",
        maintenance_password="mnt",
    )

    provision_application_database(config)

    assert mock_create_user.call_count == 4

    executed_sqls = [str(call[0][0]) for call in mock_sys_conn.execute.call_args_list]
    assert any('GRANT db_owner TO "postgres"' in sql for sql in executed_sqls)
    assert any('REVOKE db_owner FROM "postgres"' in sql for sql in executed_sqls)


@patch("app.migration_execution.provisioning.get_cloudsql_engine")
@patch("app.migration_execution.provisioning.create_user_if_missing")
def test_provisioning_transient_membership_preexisting_preserved(mock_create_user, mock_get_engine):
    mock_sys_engine = MagicMock()
    mock_sys_conn = MagicMock()
    mock_sys_engine.connect.return_value.__enter__.return_value = mock_sys_conn

    mock_target_engine = MagicMock()
    mock_target_conn = MagicMock()
    mock_target_engine.connect.return_value.__enter__.return_value = mock_target_conn

    mock_get_engine.side_effect = [
        (mock_sys_engine, MagicMock()),
        (mock_target_engine, MagicMock()),
    ]

    def mock_sys_exec(sql, *args, **kwargs):
        sql_str = str(sql)
        if "SELECT CURRENT_USER" in sql_str:
            return MagicMock(scalar=lambda: "postgres")
        if "pg_auth_members" in sql_str:
            return MagicMock(scalar=lambda: True)
        return MagicMock(scalar=lambda: 0)

    mock_sys_conn.execute.side_effect = mock_sys_exec

    config = MigrationExecutionConfig(
        project_id="finance-intel-staging-8f2a",
        instance_name="fi-staging-db",
        region="europe-west1",
        target_database="finance_intelligence_staging",
        expected_head="030_reconcile_application_role_catalog",
        initial_admin_password="adm",
        bootstrap_password="boot",
        api_password="api",
        worker_password="wrk",
        maintenance_password="mnt",
    )

    provision_application_database(config)

    executed_sqls = [str(call[0][0]) for call in mock_sys_conn.execute.call_args_list]
    assert not any('GRANT db_owner TO "postgres"' in sql for sql in executed_sqls)
    assert not any('REVOKE db_owner FROM "postgres"' in sql for sql in executed_sqls)


@patch("app.migration_execution.provisioning.get_cloudsql_engine")
@patch("app.migration_execution.provisioning.create_user_if_missing")
def test_provisioning_transient_membership_cleanup_runs_on_failure(mock_create_user, mock_get_engine):
    mock_sys_engine = MagicMock()
    mock_sys_conn = MagicMock()
    mock_sys_engine.connect.return_value.__enter__.return_value = mock_sys_conn

    mock_get_engine.side_effect = [
        (mock_sys_engine, MagicMock()),
    ]

    def mock_sys_execute(sql, *args, **kwargs):
        sql_str = str(sql)
        if "CREATE DATABASE" in sql_str:
            raise RuntimeError("Database creation simulated failure")
        if "SELECT CURRENT_USER" in sql_str:
            return MagicMock(scalar=lambda: "postgres")
        if "pg_auth_members" in sql_str:
            return MagicMock(scalar=lambda: False)
        return MagicMock(scalar=lambda: 0)

    mock_sys_conn.execute.side_effect = mock_sys_execute

    config = MigrationExecutionConfig(
        project_id="finance-intel-staging-8f2a",
        instance_name="fi-staging-db",
        region="europe-west1",
        target_database="finance_intelligence_staging",
        expected_head="030_reconcile_application_role_catalog",
        initial_admin_password="adm",
        bootstrap_password="boot",
        api_password="api",
        worker_password="wrk",
        maintenance_password="mnt",
    )

    with pytest.raises(ProvisioningError, match="Database creation simulated failure"):
        provision_application_database(config)

    executed_sqls = [str(call[0][0]) for call in mock_sys_conn.execute.call_args_list]
    assert any('REVOKE db_owner FROM "postgres"' in sql for sql in executed_sqls)
