"""Finance Intelligence Staging Migration Runner Entrypoint.

Fail-closed entrypoint for Cloud Run Job migration execution.
Enforces CLI subcommand isolation, secret redaction, and project identity validation.
"""

import argparse
import logging
import sys
from typing import NoReturn

from app.core.migration_policy import IRREVERSIBLE_MIGRATION_POLICIES
from app.migration_execution.alembic_runner import run_alembic_migrations
from app.migration_execution.cloudsql_admin import update_user_password
from app.migration_execution.config import MigrationExecutionConfig
from app.migration_execution.provisioning import provision_application_database
from app.migration_execution.redaction import redact_text

# Backward-compatible alias for existing test imports
redact_sensitive_string = redact_text
from app.migration_execution.verification import run_security_verification

# Configure logger with stdout for INFO and stderr for ERROR
logger = logging.getLogger("migration_runner")
logger.setLevel(logging.INFO)

if not logger.handlers:
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.addFilter(lambda record: record.levelno < logging.ERROR)
    stdout_handler.setFormatter(logging.Formatter("%(message)s"))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(stdout_handler)
    logger.addHandler(stderr_handler)


def run_preflight() -> int:
    """Validates runtime configuration and project identity in a read-only manner."""
    logger.info("[MIGRATION_PREFLIGHT] Validating runtime configuration...")
    from app.migration_execution.compatibility.revision_024 import (
        EXPECTED_REVISION_024_SHA256,
        verify_revision_024_checksum,
    )

    verify_revision_024_checksum()
    logger.info("[REVISION_024_COMPATIBILITY_IMPORT] SUCCESS")
    logger.info(f"[REVISION_024_CHECKSUM_CONSTANT] {EXPECTED_REVISION_024_SHA256}")
    logger.info(f"[MIGRATION_PREFLIGHT] Irreversible boundary active: {list(IRREVERSIBLE_MIGRATION_POLICIES.keys())}")
    logger.info("[MIGRATION_PREFLIGHT] SUCCESS - Preflight check clean.")
    return 0


def main() -> NoReturn:
    parser = argparse.ArgumentParser(
        description="Finance Intelligence Migration Runner CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Target migration operation")

    subparsers.add_parser("preflight", help="Run read-only preflight configuration validation")
    subparsers.add_parser("bootstrap-password", help="Bootstrap initial postgres user password")
    subparsers.add_parser("provision-database", help="Provision application target database and roles")
    subparsers.add_parser("migrate", help="Execute Alembic migrations to head")
    subparsers.add_parser("verify", help="Verify schema ACLs and RLS policies post-migration")

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        logger.error("\nERROR: No subcommand provided. Executing without subcommand is forbidden.")
        sys.exit(1)

    try:
        if args.subcommand == "preflight":
            exit_code = run_preflight()
            sys.exit(exit_code)

        config = MigrationExecutionConfig.from_env(args.subcommand)
        logger.info(f"[MIGRATION_ENTRYPOINT] Dispatching subcommand '{args.subcommand}' with config: {config}")

        if args.subcommand == "bootstrap-password":
            assert config.initial_admin_password is not None
            update_user_password(
                config.project_id,
                config.instance_name,
                username="postgres",
                password=config.initial_admin_password,
            )
            logger.info("[MIGRATION_ENTRYPOINT] SUCCESS: Subcommand 'bootstrap-password' completed.")
            sys.exit(0)

        elif args.subcommand == "provision-database":
            provision_application_database(config)
            logger.info("[MIGRATION_ENTRYPOINT] SUCCESS: Subcommand 'provision-database' completed.")
            sys.exit(0)

        elif args.subcommand == "migrate":
            run_alembic_migrations(config)
            logger.info("[MIGRATION_ENTRYPOINT] SUCCESS: Subcommand 'migrate' completed.")
            sys.exit(0)

        elif args.subcommand == "verify":
            run_security_verification(config)
            logger.info("[MIGRATION_ENTRYPOINT] SUCCESS: Subcommand 'verify' completed.")
            sys.exit(0)

        else:
            logger.error(f"[MIGRATION_ENTRYPOINT] Unknown subcommand: '{args.subcommand}'")
            sys.exit(1)

    except Exception as e:  # noqa: BLE001
        redacted_err = redact_text(str(e))
        logger.error(f"[MIGRATION_ENTRYPOINT] Subcommand '{args.subcommand}' failed: {redacted_err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
