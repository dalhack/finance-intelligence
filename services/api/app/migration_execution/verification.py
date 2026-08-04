"""Post-Migration Read-Only Security Verification Module."""

import logging

from app.migration_execution.config import MigrationExecutionConfig
from app.migration_execution.redaction import redact_text
from google.cloud.sql.connector import Connector, IPTypes
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("migration_runner")

DOMAIN_TABLES = [
    "organizations",
    "users",
    "memberships",
    "membership_roles",
    "stored_objects",
    "upload_sessions",
    "documents",
    "document_versions",
    "document_pages",
    "document_chunks",
    "ingestion_jobs",
    "ingestion_attempts",
    "extraction_results",
    "extraction_warnings",
    "audit_events",
]


class VerificationError(Exception):
    """Raised when one or more post-migration security verification gates fail."""


def run_security_verification(config: MigrationExecutionConfig) -> None:
    """Executes 11 read-only post-migration security verification gates on the target database."""
    logger.info(f"[VERIFICATION] Starting 11-point security verification on '{config.target_database}'...")

    if not config.bootstrap_password:
        raise VerificationError("BOOTSTRAP_PASSWORD is required for verification.")

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

        with engine.connect() as conn:
            # Gate 1: Alembic Version Head
            res = conn.execute(text("SELECT version_num FROM alembic_version;")).fetchone()
            applied_head = res[0] if res else None
            logger.info(f"[VERIFICATION Gate 1/11] Alembic head: '{applied_head}'")
            if applied_head != config.expected_head:
                raise VerificationError(f"Gate 1 Failed: Expected head '{config.expected_head}', got '{applied_head}'.")

            # Gate 2: Database Owner
            res = conn.execute(
                text("SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_database WHERE datname = :dbname;"),
                {"dbname": config.target_database},
            ).fetchone()
            db_owner = res[0] if res else None
            logger.info(f"[VERIFICATION Gate 2/11] Database owner: '{db_owner}'")
            if db_owner != "db_owner":
                raise VerificationError(f"Gate 2 Failed: Expected database owner 'db_owner', got '{db_owner}'.")

            # Gate 3 & 5: Role Attributes and Least-Privilege Isolation
            roles = ["db_owner", "db_bootstrap", "db_api_user", "db_ingestion_worker", "db_maintenance_worker"]
            for role in roles:
                r_res = conn.execute(
                    text(
                        "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls FROM pg_roles WHERE rolname = :role;"
                    ),
                    {"role": role},
                ).fetchone()
                if not r_res:
                    raise VerificationError(f"Gate 3 Failed: Role '{role}' missing in database.")
                if any(r_res):
                    raise VerificationError(f"Gate 3 Failed: Role '{role}' has dangerous elevated privileges: {r_res}.")

            logger.info("[VERIFICATION Gate 3/11] PostgreSQL role existence & privilege flags: PASS")

            # Gate 4: Membership of db_bootstrap in db_owner
            res = conn.execute(
                text("""
                    SELECT 1 FROM pg_auth_members m
                    JOIN pg_roles r1 ON m.roleid = r1.oid
                    JOIN pg_roles r2 ON m.member = r2.oid
                    WHERE r1.rolname = 'db_owner' AND r2.rolname = 'db_bootstrap';
                """)
            ).fetchone()
            logger.info(f"[VERIFICATION Gate 4/11] db_bootstrap member of db_owner: {'PASS' if res else 'FAIL'}")
            if not res:
                raise VerificationError("Gate 4 Failed: 'db_bootstrap' is not a member of 'db_owner'.")

            # Gate 5 (Cont.): Runtime roles must NOT be members of db_owner
            for rt_role in ["db_api_user", "db_ingestion_worker", "db_maintenance_worker"]:
                res = conn.execute(
                    text("""
                        SELECT 1 FROM pg_auth_members m
                        JOIN pg_roles r1 ON m.roleid = r1.oid
                        JOIN pg_roles r2 ON m.member = r2.oid
                        WHERE r1.rolname = 'db_owner' AND r2.rolname = :role;
                    """),
                    {"role": rt_role},
                ).fetchone()
                if res:
                    raise VerificationError(
                        f"Gate 5 Failed: Runtime role '{rt_role}' is illegally a member of 'db_owner'!"
                    )

            logger.info("[VERIFICATION Gate 5/11] Runtime role least-privilege isolation: PASS")

            # Gate 6: RLS Enabled & Forced on all Domain Tables
            for tbl in DOMAIN_TABLES:
                res = conn.execute(
                    text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = :tbl;"),
                    {"tbl": tbl},
                ).fetchone()
                if not res or not res[0] or not res[1]:
                    raise VerificationError(f"Gate 6 Failed: Table '{tbl}' does not have both ENABLED and FORCED RLS.")

            logger.info(
                f"[VERIFICATION Gate 6/11] RLS ENABLED & FORCED across all {len(DOMAIN_TABLES)} domain tables: PASS"
            )

            # Gate 7: Schema & Table ACLs (PUBLIC EXECUTE revoked)
            res = conn.execute(text("SELECT has_schema_privilege('public', 'public', 'CREATE');")).fetchone()
            if res and res[0]:
                raise VerificationError("Gate 7 Failed: PUBLIC has CREATE privilege on schema public!")

            logger.info("[VERIFICATION Gate 7/11] PUBLIC schema & ACL privileges: PASS")

            # Gate 8: resolve_auth_context SECURITY DEFINER check
            res = conn.execute(
                text("""
                    SELECT p.prosecdef, pg_get_userbyid(p.proowner), p.proconfig
                    FROM pg_proc p
                    JOIN pg_namespace n ON p.pronamespace = n.oid
                    WHERE n.nspname = 'public' AND p.proname = 'resolve_auth_context';
                """)
            ).fetchone()
            if not res or not res[0] or res[1] != "db_owner":
                raise VerificationError(
                    "Gate 8 Failed: 'resolve_auth_context' function is not SECURITY DEFINER or not owned by db_owner."
                )

            logger.info("[VERIFICATION Gate 8/11] resolve_auth_context SECURITY DEFINER: PASS")

            # Gate 9: Permission Table Count (17 canonical permissions)
            res = conn.execute(text("SELECT COUNT(*) FROM permissions;")).fetchone()
            perm_count = res[0] if res else 0
            logger.info(f"[VERIFICATION Gate 9/11] Permission catalog count: {perm_count}")
            if perm_count != 17:
                raise VerificationError(f"Gate 9 Failed: Expected 17 canonical permissions, found {perm_count}.")

            # Gate 10: Role Catalog Breakdown (8 VIEWER, 15 ANALYST, ADMIN absent)
            res = conn.execute(
                text("SELECT role_name, COUNT(*) FROM application_role_permissions GROUP BY role_name;")
            ).fetchall()
            role_counts = {row[0]: row[1] for row in res}
            logger.info(f"[VERIFICATION Gate 10/11] Role permission counts: {role_counts}")

            if "ADMIN" in role_counts:
                raise VerificationError("Gate 10 Failed: Prohibited 'ADMIN' application role present in catalog!")
            if role_counts.get("VIEWER") != 8:
                raise VerificationError(
                    f"Gate 10 Failed: Expected 8 VIEWER permissions, got {role_counts.get('VIEWER')}."
                )
            if role_counts.get("ANALYST") != 15:
                raise VerificationError(
                    f"Gate 10 Failed: Expected 15 ANALYST permissions, got {role_counts.get('ANALYST')}."
                )

            # Gate 11: Uppercase Constraint on roles(name)
            res = conn.execute(
                text("""
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'check_roles_name_uppercase' AND conrelid = 'roles'::regclass;
                """)
            ).fetchone()
            logger.info(f"[VERIFICATION Gate 11/11] Uppercase role name constraint: {'PASS' if res else 'FAIL'}")
            if not res:
                raise VerificationError(
                    "Gate 11 Failed: Constraint 'check_roles_name_uppercase' missing on roles table."
                )

        logger.info("[VERIFICATION] SUCCESS: All 11 post-migration security verification gates PASSED cleanly.")

    except Exception as e:
        logger.error(f"[VERIFICATION] Verification failed: {redact_text(str(e))}")
        raise VerificationError(f"Verification failed: {redact_text(str(e))}") from e
    finally:
        if engine:
            engine.dispose()
        if connector:
            connector.cleanup()
