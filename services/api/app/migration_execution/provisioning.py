"""Database and PostgreSQL Role Provisioning Module."""

import logging

from app.migration_execution.cloudsql_admin import create_user_if_missing
from app.migration_execution.config import MigrationExecutionConfig
from app.migration_execution.redaction import redact_text
from google.cloud.sql.connector import Connector, IPTypes
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("migration_runner")


class ProvisioningError(Exception):
    """Raised when database or role provisioning fails."""


def get_cloudsql_engine(
    config: MigrationExecutionConfig,
    user: str,
    password: str,
    database: str = "postgres",
    autocommit: bool = False,
) -> tuple[Engine, Connector]:
    """Creates a SQLAlchemy engine connected to Cloud SQL via Private IP Connector."""
    connector = Connector()

    def getconn():
        conn = connector.connect(
            f"{config.project_id}:{config.region}:{config.instance_name}",
            "pg8000",
            user=user,
            password=password,
            db=database,
            ip_type=IPTypes.PRIVATE,
        )
        return conn

    engine = create_engine("postgresql+pg8000://", creator=getconn)
    if autocommit:
        engine = engine.execution_options(isolation_level="AUTOCOMMIT")

    return engine, connector


def create_role_if_missing_sql(engine: Engine, role_name: str, is_login: bool = False) -> None:
    """Idempotently creates a PostgreSQL role using SQL statements."""
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role_name})
        if res.scalar():
            logger.info(f"[PROVISIONING] Role '{role_name}' already exists.")
            return

        login_clause = "LOGIN" if is_login else "NOLOGIN"
        logger.info(f"[PROVISIONING] Creating role '{role_name}' ({login_clause})...")
        conn.execute(
            text(
                f"CREATE ROLE {role_name} WITH {login_clause} NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION;"
            )
        )


def provision_application_database(config: MigrationExecutionConfig) -> None:
    """Provisions the target application database and prerequisite roles."""
    logger.info(f"[PROVISIONING] Starting provisioning for target database '{config.target_database}'...")

    if not config.initial_admin_password:
        raise ProvisioningError("INITIAL_ADMIN_PASSWORD is required for provisioning.")

    sys_engine: Engine | None = None
    sys_connector: Connector | None = None

    try:
        sys_engine, sys_connector = get_cloudsql_engine(
            config,
            user="postgres",
            password=config.initial_admin_password,
            database="postgres",
            autocommit=True,
        )

        # 1. Idempotently create NOLOGIN owner and legacy roles
        create_role_if_missing_sql(sys_engine, "db_owner", is_login=False)
        create_role_if_missing_sql(sys_engine, "db_app_user", is_login=False)

        # 2. Idempotently create or update LOGIN roles via Cloud SQL Admin API (or fallback if passwords present)
        login_roles = {
            "db_bootstrap": config.bootstrap_password,
            "db_api_user": config.api_password,
            "db_ingestion_worker": config.worker_password,
            "db_maintenance_worker": config.maintenance_password,
        }

        for role_name, pwd in login_roles.items():
            if pwd:
                create_user_if_missing(
                    config.project_id,
                    config.instance_name,
                    username=role_name,
                    password=pwd,
                )
            else:
                logger.info(
                    f"[PROVISIONING] Secret for '{role_name}' not provided in environment. Ensuring role exists in SQL..."
                )
                create_role_if_missing_sql(sys_engine, role_name, is_login=True)

        # 3. Verify and set role attributes & memberships via SQL
        with sys_engine.connect() as conn:
            # Grant db_owner membership to db_bootstrap
            logger.info("[PROVISIONING] Granting 'db_owner' membership to 'db_bootstrap'...")
            conn.execute(text("GRANT db_owner TO db_bootstrap;"))

            # Check if target database exists
            res = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": config.target_database},
            )
            if not res.scalar():
                logger.info(f"[PROVISIONING] Creating database '{config.target_database}' WITH OWNER db_owner...")
                conn.execute(text(f"CREATE DATABASE {config.target_database} OWNER db_owner;"))
            else:
                logger.info(f"[PROVISIONING] Database '{config.target_database}' already exists.")
                conn.execute(text(f"ALTER DATABASE {config.target_database} OWNER TO db_owner;"))

            # Connect privileges
            conn.execute(
                text(
                    f"GRANT CONNECT ON DATABASE {config.target_database} TO db_bootstrap, db_api_user, db_ingestion_worker, db_maintenance_worker;"
                )
            )

        # 4. Target DB schema privileges
        target_engine, target_connector = get_cloudsql_engine(
            config,
            user="postgres",
            password=config.initial_admin_password,
            database=config.target_database,
            autocommit=True,
        )

        try:
            with target_engine.connect() as conn:
                logger.info(f"[PROVISIONING] Setting schema public privileges on '{config.target_database}'...")
                conn.execute(text("GRANT ALL ON SCHEMA public TO db_owner;"))
                conn.execute(text("ALTER SCHEMA public OWNER TO db_owner;"))
                conn.execute(
                    text(
                        "GRANT USAGE ON SCHEMA public TO db_bootstrap, db_api_user, db_ingestion_worker, db_maintenance_worker;"
                    )
                )
        finally:
            target_engine.dispose()
            target_connector.close()

        logger.info(f"[PROVISIONING] SUCCESS: Database '{config.target_database}' and roles provisioned cleanly.")

    except Exception as e:
        logger.error(f"[PROVISIONING] Provisioning failed: {redact_text(str(e))}")
        raise ProvisioningError(f"Provisioning failed: {redact_text(str(e))}") from e
    finally:
        if sys_engine:
            sys_engine.dispose()
        if sys_connector:
            sys_connector.close()
