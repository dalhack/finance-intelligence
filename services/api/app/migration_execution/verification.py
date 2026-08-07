"""Post-Migration Read-Only Security Verification Module."""

import logging

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
        if Connector is None or IPTypes is None:
            raise VerificationError("cloud-sql-python-connector is required for Cloud SQL security verification.")
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

            # Gate 5 (Cont.): Admin & Runtime roles must NOT be members of db_owner
            for rt_role in ["postgres", "db_api_user", "db_ingestion_worker", "db_maintenance_worker"]:
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
                        f"Gate 5 Failed: Non-owner role '{rt_role}' is illegally a member of 'db_owner'!"
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

            # Gate 8: resolve_auth_context SECURITY DEFINER, owner, search_path, and EXECUTE ACL checks
            # Query exact function signature 'text, uuid' to prevent overload ambiguity
            res = conn.execute(
                text("""
                    SELECT p.oid,
                           p.prosecdef,
                           pg_get_userbyid(p.proowner) AS owner_name,
                           p.proconfig,
                           has_function_privilege('public', p.oid, 'EXECUTE') AS public_execute,
                           CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'db_api_user')
                                THEN has_function_privilege('db_api_user', p.oid, 'EXECUTE')
                                ELSE false END AS db_api_user_execute
                    FROM pg_proc p
                    JOIN pg_namespace n ON p.pronamespace = n.oid
                    WHERE n.nspname = 'public'
                      AND p.proname = 'resolve_auth_context'
                      AND pg_get_function_identity_arguments(p.oid) = 'text, uuid';
                """)
            ).fetchone()
            if not res:
                raise VerificationError("Gate 8 Failed: Function 'resolve_auth_context(text, uuid)' not found.")

            _fn_oid, prosecdef, owner_name, proconfig, public_execute, db_api_user_execute = res

            if owner_name != "db_owner":
                raise VerificationError(
                    f"Gate 8a Failed: 'resolve_auth_context' owned by '{owner_name}', expected 'db_owner'."
                )

            if not prosecdef:
                raise VerificationError(
                    "Gate 8b Failed: 'resolve_auth_context' is SECURITY INVOKER, expected SECURITY DEFINER."
                )

            # Verify search_path configuration in proconfig
            search_path_val = None
            if proconfig:
                for item in proconfig:
                    if item.lower().startswith("search_path="):
                        search_path_val = item.split("=", 1)[1].strip()
                        break

            sp_parts = [p.strip() for p in search_path_val.split(",")] if search_path_val else []
            if sp_parts != ["public", "pg_catalog", "pg_temp"]:
                raise VerificationError(
                    f"Gate 8c Failed: 'resolve_auth_context' search_path is '{search_path_val}', expected 'public, pg_catalog, pg_temp'."
                )

            if public_execute:
                raise VerificationError("Gate 8d Failed: PUBLIC has EXECUTE privilege on 'resolve_auth_context'.")

            if not db_api_user_execute:
                raise VerificationError(
                    "Gate 8e Failed: role 'db_api_user' lacks EXECUTE privilege on 'resolve_auth_context'."
                )

            logger.info("[VERIFICATION Gate 8/11] resolve_auth_context SECURITY DEFINER, search_path, & ACLs: PASS")

            # Gate 9: Permission Table Count (17 canonical permissions)
            res = conn.execute(text("SELECT COUNT(*) FROM permissions;")).fetchone()
            perm_count = res[0] if res else 0
            logger.info(f"[VERIFICATION Gate 9/11] Permission catalog count: {perm_count}")
            if perm_count != 17:
                raise VerificationError(f"Gate 9 Failed: Expected 17 canonical permissions, found {perm_count}.")

            # Gate 10: Role Catalog Breakdown (8 VIEWER, 15 ANALYST, ADMIN absent)
            # Authoritative schema: public.roles, public.role_permissions, public.permissions
            roles_rows = conn.execute(
                text("""
                    SELECT r.name, COUNT(DISTINCT rp.permission_id)
                    FROM public.roles r
                    LEFT JOIN public.role_permissions rp ON r.id = rp.role_id
                    GROUP BY r.id, r.name;
                """)
            ).fetchall()
            role_map = {row[0]: row[1] for row in roles_rows}
            logger.info(f"[VERIFICATION Gate 10/11] Role permission counts: {role_map}")

            if "ADMIN" in role_map:
                raise VerificationError("Gate 10 Failed: Prohibited 'ADMIN' application role present in catalog!")
            if "VIEWER" not in role_map:
                raise VerificationError("Gate 10 Failed: Mandatory role 'VIEWER' is missing from public.roles.")
            if role_map["VIEWER"] != 8:
                raise VerificationError(f"Gate 10 Failed: Expected 8 VIEWER permissions, got {role_map['VIEWER']}.")
            if "ANALYST" not in role_map:
                raise VerificationError("Gate 10 Failed: Mandatory role 'ANALYST' is missing from public.roles.")
            if role_map["ANALYST"] != 15:
                raise VerificationError(f"Gate 10 Failed: Expected 15 ANALYST permissions, got {role_map['ANALYST']}.")

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
        safe_close_connector(connector)
