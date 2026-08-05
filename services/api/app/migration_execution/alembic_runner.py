"""Alembic Migration Execution Runner with Session-Bound Advisory Locking."""

import logging
import os

from alembic import command
from alembic.config import Config
from app.migration_execution.config import MigrationExecutionConfig
from app.migration_execution.redaction import redact_text, safe_close_connector
from google.cloud.sql.connector import Connector, IPTypes
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("migration_runner")

MIGRATION_ADVISORY_LOCK_ID = 849204918239


class MigrationRunnerError(Exception):
    """Raised when Alembic migration execution fails or boundary is violated."""


def run_alembic_migrations(config: MigrationExecutionConfig) -> None:
    """Executes Alembic migrations to head on the target database using session-level locking."""
    logger.info(f"[MIGRATION_RUNNER] Starting migration execution on '{config.target_database}'...")

    if not config.bootstrap_password:
        raise MigrationRunnerError("BOOTSTRAP_PASSWORD is required to run migrations.")

    connector: Connector | None = None
    engine: Engine | None = None

    try:
        connector = Connector()

        def getconn():
            return connector.connect(
                f"{config.project_id}:{config.region}:{config.instance_name}",
                "pg8000",
                user="db_bootstrap",
                password=config.bootstrap_password,
                db=config.target_database,
                ip_type=IPTypes.PRIVATE,
            )

        engine = create_engine("postgresql+pg8000://", creator=getconn)

        with engine.connect() as connection:
            logger.info("[MIGRATION_RUNNER] Setting active role to 'db_owner'...")
            connection.execute(text("SET ROLE db_owner;"))

            # Verify session and current user identity
            user_check = connection.execute(text("SELECT session_user, current_user;")).fetchone()
            if user_check:
                logger.info(f"[MIGRATION_RUNNER] Session user: '{user_check[0]}', Current role: '{user_check[1]}'")
                if user_check[1] != "db_owner":
                    raise MigrationRunnerError(f"Role activation failed. Expected 'db_owner', got '{user_check[1]}'.")

            # Acquire session-level advisory lock
            logger.info(f"[MIGRATION_RUNNER] Acquiring advisory lock ({MIGRATION_ADVISORY_LOCK_ID})...")
            connection.execute(text(f"SELECT pg_advisory_lock({MIGRATION_ADVISORY_LOCK_ID});"))
            logger.info(f"[MIGRATION_RUNNER] Advisory lock ({MIGRATION_ADVISORY_LOCK_ID}) acquired.")

            try:
                # Locate alembic.ini path
                ini_path = os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
                if not os.path.exists(ini_path):
                    ini_path = "/app/services/api/alembic.ini"

                alembic_cfg = Config(ini_path)
                # Pass the active connection object directly to Alembic
                alembic_cfg.attributes["connection"] = connection

                logger.info(f"[MIGRATION_RUNNER] Executing Alembic upgrade to '{config.expected_head}'...")
                command.upgrade(alembic_cfg, "head")

                # Verify applied head in alembic_version table
                res = connection.execute(text("SELECT version_num FROM alembic_version;")).fetchone()
                applied_head = res[0] if res else None
                logger.info(f"[MIGRATION_RUNNER] Alembic version table head: '{applied_head}'")

                if applied_head != config.expected_head:
                    raise MigrationRunnerError(
                        f"Migration head mismatch! Expected '{config.expected_head}', got '{applied_head}'."
                    )

                logger.info(f"[MIGRATION_RUNNER] SUCCESS: Applied migration head verified at '{applied_head}'.")

            finally:
                # Release advisory lock in finally block
                logger.info(f"[MIGRATION_RUNNER] Releasing advisory lock ({MIGRATION_ADVISORY_LOCK_ID})...")
                connection.execute(text(f"SELECT pg_advisory_unlock({MIGRATION_ADVISORY_LOCK_ID});"))

    except Exception as e:
        logger.error(f"[MIGRATION_RUNNER] Migration failed: {redact_text(str(e))}")
        raise MigrationRunnerError(f"Migration execution failed: {redact_text(str(e))}") from e
    finally:
        if engine:
            engine.dispose()
        safe_close_connector(connector)
