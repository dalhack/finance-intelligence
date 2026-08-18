"""Migration Execution Configuration and Environment Validation."""

import os
from dataclasses import dataclass


class MigrationConfigError(Exception):
    """Raised when migration configuration is invalid or missing required variables."""


# Exact Allowlisted Non-Secret Configuration Defaults
ALLOWED_PROJECT_ID = "finance-intel-staging-8f2a"
ALLOWED_INSTANCE_NAME = "fi-staging-db"
ALLOWED_REGION = "europe-west1"
ALLOWED_TARGET_DATABASE = "finance_intelligence_staging"
ALLOWED_MIGRATION_HEAD = "036_analysis_plane_tenant_isolation_fail_closed"


@dataclass(frozen=True)
class MigrationExecutionConfig:
    project_id: str
    instance_name: str
    region: str
    target_database: str
    expected_head: str

    initial_admin_password: str | None = None
    bootstrap_password: str | None = None
    api_password: str | None = None
    worker_password: str | None = None
    maintenance_password: str | None = None

    def __repr__(self) -> str:
        return (
            f"MigrationExecutionConfig("
            f"project_id='{self.project_id}', "
            f"instance_name='{self.instance_name}', "
            f"region='{self.region}', "
            f"target_database='{self.target_database}', "
            f"expected_head='{self.expected_head}', "
            f"initial_admin_password={'[SET]' if self.initial_admin_password else '[ABSENT]'}, "
            f"bootstrap_password={'[SET]' if self.bootstrap_password else '[ABSENT]'}, "
            f"api_password={'[SET]' if self.api_password else '[ABSENT]'}, "
            f"worker_password={'[SET]' if self.worker_password else '[ABSENT]'}, "
            f"maintenance_password={'[SET]' if self.maintenance_password else '[ABSENT]'}')"
        )

    @classmethod
    def from_env(cls, subcommand: str) -> "MigrationExecutionConfig":
        """Loads and validates configuration from environment variables for the given subcommand."""

        project_id = os.environ.get("GCP_PROJECT", ALLOWED_PROJECT_ID).strip()
        instance_name = os.environ.get("CLOUD_SQL_INSTANCE", ALLOWED_INSTANCE_NAME).strip()
        region = os.environ.get("REGION", ALLOWED_REGION).strip()
        target_database = os.environ.get("TARGET_DATABASE", ALLOWED_TARGET_DATABASE).strip()
        expected_head = os.environ.get("EXPECTED_MIGRATION_HEAD", ALLOWED_MIGRATION_HEAD).strip()

        # Reject prohibited values or unexpected environments
        if project_id != ALLOWED_PROJECT_ID:
            raise MigrationConfigError(f"Invalid GCP_PROJECT: '{project_id}'. Expected '{ALLOWED_PROJECT_ID}'.")
        if instance_name != ALLOWED_INSTANCE_NAME:
            raise MigrationConfigError(
                f"Invalid CLOUD_SQL_INSTANCE: '{instance_name}'. Expected '{ALLOWED_INSTANCE_NAME}'."
            )
        if region != ALLOWED_REGION:
            raise MigrationConfigError(f"Invalid REGION: '{region}'. Expected '{ALLOWED_REGION}'.")
        if target_database != ALLOWED_TARGET_DATABASE:
            raise MigrationConfigError(
                f"Invalid TARGET_DATABASE: '{target_database}'. Expected '{ALLOWED_TARGET_DATABASE}'."
            )
        if expected_head != ALLOWED_MIGRATION_HEAD:
            raise MigrationConfigError(
                f"Invalid EXPECTED_MIGRATION_HEAD: '{expected_head}'. Expected '{ALLOWED_MIGRATION_HEAD}'."
            )

        for val in (project_id, instance_name, region, target_database, expected_head):
            if "travel-mapper" in val.lower() or "travel_mapper" in val.lower():
                raise MigrationConfigError("Prohibited Travel Mapper context detected in migration configuration.")

        initial_admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD")
        bootstrap_password = os.environ.get("BOOTSTRAP_PASSWORD")
        api_password = os.environ.get("API_PASSWORD")
        worker_password = os.environ.get("WORKER_PASSWORD")
        maintenance_password = os.environ.get("MAINTENANCE_PASSWORD")

        # Validate required secrets per subcommand
        if subcommand == "bootstrap-password":
            if not initial_admin_password:
                raise MigrationConfigError("Missing required environment variable: INITIAL_ADMIN_PASSWORD")
        elif subcommand in ("provision-database", "reconcile-role-membership-attributes"):
            if not initial_admin_password:
                raise MigrationConfigError("Missing required environment variable: INITIAL_ADMIN_PASSWORD")
            if subcommand == "provision-database" and not bootstrap_password:
                raise MigrationConfigError("Missing required environment variable: BOOTSTRAP_PASSWORD")
        elif subcommand in ("migrate", "verify") and not bootstrap_password:
            raise MigrationConfigError("Missing required environment variable: BOOTSTRAP_PASSWORD")

        return cls(
            project_id=project_id,
            instance_name=instance_name,
            region=region,
            target_database=target_database,
            expected_head=expected_head,
            initial_admin_password=initial_admin_password,
            bootstrap_password=bootstrap_password,
            api_password=api_password,
            worker_password=worker_password,
            maintenance_password=maintenance_password,
        )
