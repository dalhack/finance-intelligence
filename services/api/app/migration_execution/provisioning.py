"""Database and PostgreSQL Role Provisioning Module."""

import logging
import re

from app.migration_execution.cloudsql_admin import create_user_if_missing
from app.migration_execution.config import MigrationExecutionConfig
from app.migration_execution.redaction import redact_text, safe_close_connector

try:
    from google.cloud.sql.connector import Connector, IPTypes
except ImportError:
    Connector = None  # type: ignore[assignment,misc]
    IPTypes = None  # type: ignore[assignment,misc]

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("migration_runner")

_ROLE_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_]+$")


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
    if Connector is None or IPTypes is None:
        raise ProvisioningError("cloud-sql-python-connector is required for Cloud SQL engine provisioning.")
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
    if not _ROLE_NAME_REGEX.match(role_name):
        raise ProvisioningError(f"Invalid role name: '{role_name}'")

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


def _check_membership(conn, parent_role: str, member_user: str) -> bool:
    """Checks if member_user is a member of parent_role in pg_auth_members."""
    res = conn.execute(
        text(
            "SELECT 1 FROM pg_auth_members m "
            "JOIN pg_roles r_parent ON m.roleid = r_parent.oid "
            "JOIN pg_roles r_member ON m.member = r_member.oid "
            "WHERE r_parent.rolname = :parent AND r_member.rolname = :member"
        ),
        {"parent": parent_role, "member": member_user},
    )
    return bool(res.scalar())


def provision_application_database(config: MigrationExecutionConfig) -> None:
    """Provisions the target application database and prerequisite roles."""
    logger.info(f"[PROVISIONING] Starting provisioning for target database '{config.target_database}'...")

    # Upfront fail-closed secret validation: All five DB password secrets must be provided.
    required_secrets = {
        "INITIAL_ADMIN_PASSWORD": config.initial_admin_password,
        "BOOTSTRAP_PASSWORD": config.bootstrap_password,
        "API_PASSWORD": config.api_password,
        "WORKER_PASSWORD": config.worker_password,
        "MAINTENANCE_PASSWORD": config.maintenance_password,
    }
    missing = [name for name, val in required_secrets.items() if not val]
    if missing:
        raise ProvisioningError(f"Missing required environment secret(s) for provisioning: {', '.join(missing)}")

    sys_engine: Engine | None = None
    sys_connector: Connector | None = None
    target_engine: Engine | None = None
    target_connector: Connector | None = None

    temp_membership_added = False
    validated_current_user: str | None = None
    primary_exception: Exception | None = None

    try:
        sys_engine, sys_connector = get_cloudsql_engine(
            config,
            user="postgres",
            password=config.initial_admin_password,
            database="postgres",
            autocommit=True,
        )

        # 1. Idempotently create NOLOGIN owner and application roles
        create_role_if_missing_sql(sys_engine, "db_owner", is_login=False)
        create_role_if_missing_sql(sys_engine, "db_app_user", is_login=False)
        create_role_if_missing_sql(sys_engine, "db_analysis_claim_owner", is_login=False)

        # 2. Idempotently create or update LOGIN roles via Cloud SQL Admin API ONLY
        login_roles = {
            "db_bootstrap": config.bootstrap_password,
            "db_api_user": config.api_password,
            "db_ingestion_worker": config.worker_password,
            "db_maintenance_worker": config.maintenance_password,
        }

        for role_name, pwd in login_roles.items():
            assert pwd is not None
            create_user_if_missing(
                config.project_id,
                config.instance_name,
                username=role_name,
                password=pwd,
            )

        # 3. Transient membership management & database DDL via SQL
        with sys_engine.connect() as conn:
            # Query and validate current session user identity
            raw_user = conn.execute(text("SELECT CURRENT_USER;")).scalar()
            if not raw_user or not _ROLE_NAME_REGEX.match(str(raw_user)):
                raise ProvisioningError(f"Unsafe current session user identity: '{raw_user}'")
            validated_current_user = str(raw_user)

            # Check pre-existing membership
            if not _check_membership(conn, "db_owner", validated_current_user):
                logger.info(
                    f"[PROVISIONING] Granting transient 'db_owner' membership to '{validated_current_user}' for DDL operations..."
                )
                conn.execute(text(f'GRANT db_owner TO "{validated_current_user}";'))
                temp_membership_added = True
            else:
                logger.info(f"[PROVISIONING] '{validated_current_user}' already possesses 'db_owner' membership.")

            # Grant db_owner membership to db_bootstrap
            logger.info("[PROVISIONING] Granting 'db_owner' membership to 'db_bootstrap'...")
            conn.execute(text("GRANT db_owner TO db_bootstrap;"))

            # Grant db_analysis_claim_owner membership to db_owner and db_bootstrap
            logger.info(
                "[PROVISIONING] Granting 'db_analysis_claim_owner' membership to 'db_owner' and 'db_bootstrap'..."
            )
            conn.execute(text("GRANT db_analysis_claim_owner TO db_owner;"))
            conn.execute(text("GRANT db_analysis_claim_owner TO db_bootstrap;"))

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

        with target_engine.connect() as conn:
            logger.info(f"[PROVISIONING] Setting schema public privileges on '{config.target_database}'...")
            conn.execute(text("GRANT ALL ON SCHEMA public TO db_owner;"))
            conn.execute(text("ALTER SCHEMA public OWNER TO db_owner;"))
            conn.execute(
                text(
                    "GRANT USAGE ON SCHEMA public TO db_bootstrap, db_api_user, db_ingestion_worker, db_maintenance_worker;"
                )
            )

        # 5. Atomic least-privilege role security hardening
        from app.migration_execution.role_security import harden_application_login_roles

        harden_application_login_roles(sys_engine)

        logger.info(f"[PROVISIONING] SUCCESS: Database '{config.target_database}' and roles provisioned cleanly.")

    except Exception as e:
        primary_exception = e
        logger.error(f"[PROVISIONING] Provisioning failed: {redact_text(str(e))}")
        raise ProvisioningError(f"Provisioning failed: {redact_text(str(e))}") from e
    finally:
        # Cleanup target engine/connector
        if target_engine:
            target_engine.dispose()
        safe_close_connector(target_connector)

        # Cleanup transient membership on sys_engine before disposing engine
        if sys_engine and temp_membership_added and validated_current_user:
            try:
                with sys_engine.connect() as cleanup_conn:
                    logger.info(
                        f"[PROVISIONING] Revoking transient 'db_owner' membership from '{validated_current_user}'..."
                    )
                    cleanup_conn.execute(text(f'REVOKE db_owner FROM "{validated_current_user}";'))

                    # Explicit verification of revocation
                    if _check_membership(cleanup_conn, "db_owner", validated_current_user):
                        msg = f"Failed to revoke transient 'db_owner' membership from '{validated_current_user}'"
                        logger.error(f"[PROVISIONING] {msg}")
                        if primary_exception is None:
                            raise ProvisioningError(msg)
                    else:
                        logger.info(
                            f"[PROVISIONING] Transient 'db_owner' membership from '{validated_current_user}' successfully revoked and verified absent."
                        )
            except Exception as cleanup_err:
                logger.error(f"[PROVISIONING] Transient membership cleanup failed: {redact_text(str(cleanup_err))}")
                if primary_exception is None:
                    raise ProvisioningError(
                        f"Transient membership cleanup failed: {redact_text(str(cleanup_err))}"
                    ) from cleanup_err

        if sys_engine:
            sys_engine.dispose()
        safe_close_connector(sys_connector)
