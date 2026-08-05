"""Unit tests for Migration Execution Plane Modules."""

import json
import os
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from app.migration_execution.cloudsql_admin import (
    CloudSQLAdminError,
    create_user_if_missing,
    list_instance_users,
    update_user_password,
)
from app.migration_execution.config import MigrationConfigError, MigrationExecutionConfig
from app.migration_execution.redaction import redact_text, sanitize_dict_for_logging


def test_config_validation_success():
    os.environ["GCP_PROJECT"] = "finance-intel-staging-8f2a"
    os.environ["CLOUD_SQL_INSTANCE"] = "fi-staging-db"
    os.environ["REGION"] = "europe-west1"
    os.environ["TARGET_DATABASE"] = "finance_intelligence_staging"
    os.environ["EXPECTED_MIGRATION_HEAD"] = "030_reconcile_application_role_catalog"
    os.environ["INITIAL_ADMIN_PASSWORD"] = "secret_admin_pass"

    config = MigrationExecutionConfig.from_env("bootstrap-password")
    assert config.project_id == "finance-intel-staging-8f2a"
    assert config.instance_name == "fi-staging-db"
    assert config.region == "europe-west1"
    assert config.target_database == "finance_intelligence_staging"
    assert config.expected_head == "030_reconcile_application_role_catalog"
    assert config.initial_admin_password == "secret_admin_pass"


def test_config_validation_rejects_travel_mapper():
    os.environ["GCP_PROJECT"] = "finance-intel-staging-8f2a"
    os.environ["CLOUD_SQL_INSTANCE"] = "travel-mapper-db"

    with pytest.raises(MigrationConfigError, match="Invalid CLOUD_SQL_INSTANCE"):
        MigrationExecutionConfig.from_env("bootstrap-password")

    os.environ["CLOUD_SQL_INSTANCE"] = "fi-staging-db"


def test_config_validation_missing_required_secret():
    os.environ["GCP_PROJECT"] = "finance-intel-staging-8f2a"
    os.environ["CLOUD_SQL_INSTANCE"] = "fi-staging-db"
    if "INITIAL_ADMIN_PASSWORD" in os.environ:
        del os.environ["INITIAL_ADMIN_PASSWORD"]

    with pytest.raises(MigrationConfigError, match="Missing required environment variable: INITIAL_ADMIN_PASSWORD"):
        MigrationExecutionConfig.from_env("bootstrap-password")


def test_config_repr_redacts_passwords():
    config = MigrationExecutionConfig(
        project_id="finance-intel-staging-8f2a",
        instance_name="fi-staging-db",
        region="europe-west1",
        target_database="finance_intelligence_staging",
        expected_head="030_reconcile_application_role_catalog",
        initial_admin_password="super_secret_password_123",
        bootstrap_password="super_secret_password_456",
    )
    repr_str = repr(config)
    assert "super_secret_password" not in repr_str
    assert "[SET]" in repr_str


def test_redact_text_redacts_urls_and_headers():
    raw_log = (
        "Error connecting to postgresql://admin:my_secret_pwd@10.200.0.3:5432/finance_db with password=my_secret_pwd"
    )
    redacted = redact_text(raw_log)
    assert "my_secret_pwd" not in redacted
    assert "postgresql://admin:[REDACTED]@10.200.0.3:5432/finance_db" in redacted
    assert "password=[REDACTED]" in redacted


def test_sanitize_dict_for_logging():
    data = {
        "user": "postgres",
        "password": "super_secret_password",
        "nested": {"token": "bearer_123", "normal": "value"},
    }
    sanitized = sanitize_dict_for_logging(data)
    assert sanitized["user"] == "postgres"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["normal"] == "value"


# --- Cloud SQL Admin API Lifecycle Unit Tests ---


@patch("app.migration_execution.cloudsql_admin._make_api_request")
@patch("app.migration_execution.cloudsql_admin._get_authenticated_session")
def test_cloudsql_admin_update_password_success(mock_auth, mock_api):
    mock_auth.return_value = ("fake_token", MagicMock())
    mock_api.side_effect = [
        {"name": "projects/finance-intel-staging-8f2a/operations/op_123"},
        {"status": "DONE"},
    ]

    update_user_password(
        project_id="finance-intel-staging-8f2a",
        instance_name="fi-staging-db",
        username="postgres",
        password="new_password_123",
    )

    assert mock_api.call_count == 2
    assert mock_api.call_args_list[0][0][0] == "PUT"


@patch("app.migration_execution.cloudsql_admin.update_user_password")
@patch("app.migration_execution.cloudsql_admin.list_instance_users")
def test_create_user_if_missing_when_present_updates(mock_list, mock_update):
    mock_list.return_value = [{"name": "db_bootstrap"}]
    create_user_if_missing("finance-intel-staging-8f2a", "fi-staging-db", "db_bootstrap", "pwd_123")
    mock_update.assert_called_once_with(
        "finance-intel-staging-8f2a", "fi-staging-db", "db_bootstrap", "pwd_123", host="%"
    )


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
    mock_auth.return_value = ("fake_token", MagicMock())
    mock_api.side_effect = [
        {"name": "projects/finance-intel-staging-8f2a/operations/op_slow"},
        {"status": "PENDING"},
        {"status": "RUNNING"},
    ]

    with (
        patch("app.migration_execution.cloudsql_admin.time.time", side_effect=[0, 10, 30, 70]),
        pytest.raises(CloudSQLAdminError, match="timed out after 60 seconds"),
    ):
        update_user_password("finance-intel-staging-8f2a", "fi-staging-db", "postgres", "pwd_123")


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
