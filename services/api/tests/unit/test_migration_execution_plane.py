"""Unit tests for Migration Execution Plane Modules."""

import os
from unittest.mock import MagicMock, patch

import pytest
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


@patch("app.migration_execution.cloudsql_admin._make_api_request")
@patch("app.migration_execution.cloudsql_admin._get_authenticated_session")
def test_cloudsql_admin_update_password(mock_auth, mock_api):
    mock_auth.return_value = ("fake_token", MagicMock())
    mock_api.side_effect = [
        {"name": "projects/finance-intel-staging-8f2a/operations/op_123"},
        {"status": "DONE"},
    ]

    from app.migration_execution.cloudsql_admin import update_user_password

    update_user_password(
        project_id="finance-intel-staging-8f2a",
        instance_name="fi-staging-db",
        username="postgres",
        password="new_password_123",
    )

    assert mock_api.call_count == 2
