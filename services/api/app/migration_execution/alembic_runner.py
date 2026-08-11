"""Alembic Migration Execution Runner with Session-Bound Advisory Locking and Lock-Scoped Phased State Machine."""

import logging
import os

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from app.migration_execution.compatibility.revision_024 import (
    execute_compatibility_bridge,
)
from app.migration_execution.compatibility.revision_024 import (
    verify_postconditions as verify_revision_024_postconditions,
)
from app.migration_execution.config import MigrationExecutionConfig
from app.migration_execution.redaction import redact_text, safe_close_connector

try:
    from google.cloud.sql.connector import Connector, IPTypes
except ImportError:
    Connector = None  # type: ignore[assignment,misc]
    IPTypes = None  # type: ignore[assignment,misc]

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger("migration_runner")

MIGRATION_ADVISORY_LOCK_ID = 849204918239
MIGRATION_ADVISORY_LOCK_CLASSID = 197
MIGRATION_ADVISORY_LOCK_OBJID = 3096360927

from alembic.script import ScriptDirectory

KNOWN_REVISIONS = {
    None,
    "001_initial_schema_and_rls",
    "002_document_ingestion_schema",
    "003_role_separation",
    "004_revoke_app_user",
    "005_worker_claim_downgrade",
    "006_claim_tokens",
    "007_drop_legacy_overload",
    "008_facts_and_envelope",
    "009_facts_integrity",
    "010_fact_revision_uniqueness",
    "011_calculation_engine",
    "012_calc_correctness",
    "013_calc_checksum_lineage",
    "014_calc_identity_evidence",
    "015_sec_context_calc_integrity",
    "016_traceability_integrity_repair",
    "017_comparison_dataset",
    "018_comparison_dataset_correctness",
    "019_comparison_semantics_and_snapshot_integrity",
    "020_ai_orchestration_foundation",
    "021_ai_runtime_execution_integrity",
    "022_model_provider_and_analysis_events",
    "023_analysis_clarification_workflow",
    "024_maintenance_scheduler_and_operational_resilience",
    "025_distributed_provider_circuit_breaker",
    "026_public_schema_acl_hardening",
    "027_auth_context_lookup_security_plane",
    "028_remove_organization_only_actor_lookup",
    "029_analysis_authorization_policy",
    "030_reconcile_application_role_catalog",
    "031_analysis_job_claim_authority",
}


class MigrationRunnerError(Exception):
    """Raised when Alembic migration execution fails or boundary is violated."""


def get_valid_graph_revisions(alembic_cfg: Config, expected_head: str | None = None) -> set[str]:
    """Dynamically derives canonical set of valid migration revisions directly from Alembic ScriptDirectory graph with fail-closed validation."""
    try:
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        heads = script_dir.get_heads()
        if len(heads) != 1:
            raise MigrationRunnerError(f"Multiple migration heads detected in repository graph: {heads}")

        graph_head = heads[0]
        if expected_head and graph_head != expected_head:
            raise MigrationRunnerError(
                f"Repository migration graph head '{graph_head}' does not match expected_head '{expected_head}'"
            )

        revisions = {sc.revision for sc in script_dir.walk_revisions()}
        if not revisions:
            raise MigrationRunnerError("No migration revisions discovered in repository graph")

        return revisions
    except MigrationRunnerError:
        raise
    except Exception as e:
        raise MigrationRunnerError(f"Failed to derive migration revision graph: {e}") from e


def get_safe_current_revision(
    connection: Connection,
    valid_revisions: set[str] | None = None,
) -> str | None:
    """Safely inspects current database revision using Alembic MigrationContext without aborting PostgreSQL transaction if version table is absent."""
    context = MigrationContext.configure(connection)
    current_rev = context.get_current_revision()
    if connection.in_transaction():
        connection.commit()

    if current_rev is not None:
        target_revisions = valid_revisions if valid_revisions is not None else KNOWN_REVISIONS
        if current_rev not in target_revisions:
            raise MigrationRunnerError(f"Unknown or invalid migration revision detected: '{current_rev}'")

    return current_rev


def ensure_clean_transaction(connection: Connection, phase_label: str) -> None:
    """Enforces clean (transaction-free) state on the connection before/after phase boundary."""
    if connection.in_transaction():
        logger.info(f"[MIGRATION_RUNNER] Committing active transaction prior to {phase_label}...")
        connection.commit()
    assert not connection.in_transaction(), f"Connection must be clean prior to {phase_label}"


def run_alembic_migrations(config: MigrationExecutionConfig) -> None:
    """Executes Alembic migrations to head on the target database using session-level locking and phased state machine."""
    logger.info(f"[MIGRATION_RUNNER] Starting migration execution on '{config.target_database}'...")

    if not config.bootstrap_password:
        raise MigrationRunnerError("BOOTSTRAP_PASSWORD is required to run migrations.")

    connector: Connector | None = None
    engine: Engine | None = None
    lock_acquired = False

    try:
        if Connector is None or IPTypes is None:
            raise MigrationRunnerError("cloud-sql-python-connector is required to run Cloud SQL migrations.")
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

            # Verify session, current user identity, and backend PID
            identity_check = connection.execute(text("SELECT session_user, current_user, pg_backend_pid();")).fetchone()
            if not identity_check:
                raise MigrationRunnerError("Could not query session identity and backend PID.")
            sess_user, curr_user, backend_pid = identity_check
            logger.info(
                f"[MIGRATION_RUNNER] Session user: '{sess_user}', Current role: '{curr_user}', Backend PID: {backend_pid}"
            )
            if curr_user != "db_owner":
                raise MigrationRunnerError(f"Role activation failed. Expected 'db_owner', got '{curr_user}'.")

            # Acquire session-level advisory lock
            logger.info(f"[MIGRATION_RUNNER] Acquiring advisory lock ({MIGRATION_ADVISORY_LOCK_ID})...")
            connection.execute(
                text("SELECT pg_advisory_lock(:lock_id);"),
                {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
            )
            lock_acquired = True
            logger.info(f"[MIGRATION_RUNNER] Advisory lock ({MIGRATION_ADVISORY_LOCK_ID}) acquired.")

            # Commit setup transaction so connection is in clean, transaction-free state
            ensure_clean_transaction(connection, "setup completion")

            # Verify lock persistence and backend PID continuity
            lock_check = connection.execute(
                text(
                    "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND classid = :classid AND objid = :objid;"
                ),
                {
                    "classid": MIGRATION_ADVISORY_LOCK_CLASSID,
                    "objid": MIGRATION_ADVISORY_LOCK_OBJID,
                },
            ).scalar()
            if lock_check != 1:
                raise MigrationRunnerError(
                    f"Advisory lock verification failed after setup commit. Expected 1 lock, found {lock_check}."
                )

            current_pid = connection.execute(text("SELECT pg_backend_pid();")).scalar()
            if current_pid != backend_pid:
                raise MigrationRunnerError(
                    f"Backend PID mismatch after setup commit! Initial PID: {backend_pid}, Current PID: {current_pid}"
                )

            ensure_clean_transaction(connection, "migration state machine entry")

            # Locate alembic.ini path
            ini_path = os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
            if not os.path.exists(ini_path):
                ini_path = "/app/services/api/alembic.ini"

            alembic_cfg = Config(ini_path)
            alembic_cfg.attributes["connection"] = connection

            valid_revisions = get_valid_graph_revisions(alembic_cfg, config.expected_head)

            # Detect current revision safely
            current_rev = get_safe_current_revision(connection, valid_revisions)
            logger.info(f"[MIGRATION_RUNNER] Detected current database revision: '{current_rev}'")

            # PHASE 1: Standard Alembic Upgrade 001 -> 023 (if pristine or < 023)
            if current_rev is None or current_rev < "023_analysis_clarification_workflow":
                ensure_clean_transaction(connection, "Phase 1 entry")
                logger.info(
                    "[MIGRATION_RUNNER] Phase 1: Executing standard Alembic upgrade to '023_analysis_clarification_workflow'..."
                )
                command.upgrade(alembic_cfg, "023_analysis_clarification_workflow")
                ensure_clean_transaction(connection, "Phase 1 exit")

                current_rev = get_safe_current_revision(connection, valid_revisions)
                logger.info(f"[MIGRATION_RUNNER] Phase 1 committed. Revision verified at '{current_rev}'.")
                if current_rev != "023_analysis_clarification_workflow":
                    raise MigrationRunnerError(
                        f"Phase 1 verification failed! Expected '023_analysis_clarification_workflow', got '{current_rev}'."
                    )

            # PHASE 2: Production-Safe Compatibility Bridge 023 -> 024 (if at 023)
            if current_rev == "023_analysis_clarification_workflow":
                ensure_clean_transaction(connection, "Phase 2 entry")
                logger.info(
                    "[MIGRATION_RUNNER] Phase 2: Executing Revision 024 Production-Safe Compatibility Bridge..."
                )
                execute_compatibility_bridge(connection, expected_database=config.target_database)
                ensure_clean_transaction(connection, "Phase 2 exit")

                current_rev = get_safe_current_revision(connection, valid_revisions)
                logger.info(f"[MIGRATION_RUNNER] Phase 2 committed. Revision verified at '{current_rev}'.")
                if current_rev != "024_maintenance_scheduler_and_operational_resilience":
                    raise MigrationRunnerError(
                        f"Phase 2 verification failed! Expected '024_maintenance_scheduler_and_operational_resilience', got '{current_rev}'."
                    )

            # Verification of 024 catalog postconditions for 024+ resume paths
            if current_rev and current_rev >= "024_maintenance_scheduler_and_operational_resilience":
                logger.info(
                    "[MIGRATION_RUNNER] Verifying Revision 024 exact catalog postconditions prior to Phase 3..."
                )
                verify_revision_024_postconditions(connection)
                ensure_clean_transaction(connection, "024 postcondition check exit")

            # PHASE 3: Standard Alembic Upgrade 024 -> 031 (if < expected_head)
            if current_rev != config.expected_head:
                ensure_clean_transaction(connection, "Phase 3 entry")

                # Step 1: Audit pre-migration db_bootstrap schema privileges in db_owner context (direct grantee check via pg_namespace/aclexplode)
                bootstrap_create_before = bool(
                    connection.execute(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_namespace n, aclexplode(n.nspacl) a WHERE n.nspname = 'public' AND a.grantee = (SELECT oid FROM pg_roles WHERE rolname = 'db_bootstrap') AND a.privilege_type = 'CREATE');"
                        )
                    ).scalar()
                )
                bootstrap_usage_before = bool(
                    connection.execute(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_namespace n, aclexplode(n.nspacl) a WHERE n.nspname = 'public' AND a.grantee = (SELECT oid FROM pg_roles WHERE rolname = 'db_bootstrap') AND a.privilege_type = 'USAGE');"
                        )
                    ).scalar()
                )
                logger.info(
                    f"[MIGRATION_RUNNER] Pre-Phase 3 Privilege Audit: db_bootstrap USAGE={bootstrap_usage_before}, CREATE={bootstrap_create_before}"
                )

                temporary_grant_applied = False
                if not bootstrap_create_before:
                    logger.info(
                        "[MIGRATION_RUNNER] Granting bounded temporary CREATE ON SCHEMA public to db_bootstrap for Phase 3..."
                    )
                    connection.execute(text("GRANT CREATE ON SCHEMA public TO db_bootstrap;"))
                    temporary_grant_applied = True
                    ensure_clean_transaction(connection, "Temporary privilege grant")

                cleanup_verified = False
                try:
                    # RESET ROLE to restore session_user identity ('db_bootstrap') prior to Alembic upgrade.
                    # Revision 026 requires ALTER DEFAULT PRIVILEGES FOR ROLE db_bootstrap, which requires
                    # current_user to be member of db_bootstrap (or current_user == db_bootstrap).
                    logger.info(
                        "[MIGRATION_RUNNER] Resetting active role to session_user ('db_bootstrap') for Phase 3..."
                    )
                    connection.execute(text("RESET ROLE;"))

                    user_row = connection.execute(text("SELECT session_user, current_user;")).fetchone()
                    if not user_row:
                        raise MigrationRunnerError("Phase 3 session reset failed: unable to query session context.")
                    sess_user, curr_user = str(user_row[0]), str(user_row[1])
                    logger.info(
                        f"[MIGRATION_RUNNER] Phase 3 Session context: session_user='{sess_user}', current_user='{curr_user}'"
                    )
                    if curr_user != "db_bootstrap":
                        raise MigrationRunnerError(
                            f"Phase 3 session reset failed! Expected current_user 'db_bootstrap', got '{curr_user}'."
                        )

                    logger.info(f"[MIGRATION_RUNNER] Phase 3: Executing Alembic upgrade to '{config.expected_head}'...")
                    command.upgrade(alembic_cfg, config.expected_head)
                    ensure_clean_transaction(connection, "Phase 3 exit")

                    applied_head = get_safe_current_revision(connection, valid_revisions)
                    logger.info(f"[MIGRATION_RUNNER] Phase 3 committed. Revision verified at '{applied_head}'.")
                    if applied_head != config.expected_head:
                        raise MigrationRunnerError(
                            f"Phase 3 verification failed! Expected '{config.expected_head}', got '{applied_head}'."
                        )
                finally:
                    # Fail-closed temporary privilege cleanup and audit block
                    if connection and not connection.closed and not connection.invalidated:
                        try:
                            if connection.in_transaction():
                                connection.rollback()

                            connection.execute(text("SET ROLE db_owner;"))
                            if temporary_grant_applied:
                                logger.info(
                                    "[MIGRATION_RUNNER] Temporary privilege cleanup: Revoking CREATE ON SCHEMA public FROM db_bootstrap..."
                                )
                                connection.execute(text("REVOKE CREATE ON SCHEMA public FROM db_bootstrap;"))

                            bootstrap_create_after = bool(
                                connection.execute(
                                    text(
                                        "SELECT EXISTS (SELECT 1 FROM pg_namespace n, aclexplode(n.nspacl) a WHERE n.nspname = 'public' AND a.grantee = (SELECT oid FROM pg_roles WHERE rolname = 'db_bootstrap') AND a.privilege_type = 'CREATE');"
                                    )
                                ).scalar()
                            )
                            logger.info(
                                f"[MIGRATION_RUNNER] Post-Phase 3 Privilege Audit: db_bootstrap CREATE={bootstrap_create_after} (expected {bootstrap_create_before})"
                            )

                            if bootstrap_create_after != bootstrap_create_before:
                                raise MigrationRunnerError(
                                    f"Privilege parity audit failure! Expected CREATE={bootstrap_create_before}, got {bootstrap_create_after}"
                                )

                            cleanup_verified = True
                        except Exception as cleanup_ex:
                            logger.exception("[MIGRATION_RUNNER] Temporary privilege cleanup failed:")
                            if temporary_grant_applied and not cleanup_verified:
                                raise MigrationRunnerError(
                                    f"Temporary privilege cleanup failed: {cleanup_ex}"
                                ) from cleanup_ex
                if temporary_grant_applied and not cleanup_verified:
                    raise MigrationRunnerError(
                        "Privilege cleanup verification failed: temporary CREATE privilege could not be revoked."
                    )
            else:
                logger.info(
                    f"[MIGRATION_RUNNER] Database is already at target head '{config.expected_head}'. Idempotent no-op."
                )

            # Final Head Assertion and Lock Release
            final_head = get_safe_current_revision(connection, valid_revisions)
            if final_head != config.expected_head:
                raise MigrationRunnerError(
                    f"Final migration head mismatch! Expected '{config.expected_head}', got '{final_head}'."
                )

            ensure_clean_transaction(connection, "explicit unlock")

            # Verify PID continuity prior to unlock
            unlock_pid = connection.execute(text("SELECT pg_backend_pid();")).scalar()
            if unlock_pid != backend_pid:
                raise MigrationRunnerError(
                    f"Backend PID changed prior to unlock! Initial: {backend_pid}, Current: {unlock_pid}"
                )

            logger.info(f"[MIGRATION_RUNNER] Releasing advisory lock ({MIGRATION_ADVISORY_LOCK_ID})...")
            unlock_res = connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id);"),
                {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
            ).fetchone()
            unlock_ok = bool(unlock_res and unlock_res[0])
            ensure_clean_transaction(connection, "unlock completion")

            if not unlock_ok:
                raise MigrationRunnerError(
                    f"Advisory lock ({MIGRATION_ADVISORY_LOCK_ID}) unlock returned false or failed."
                )

            logger.info(
                f"[MIGRATION_RUNNER] SUCCESS: Session advisory lock released. Migration head verified at '{final_head}'."
            )

    except Exception as e:
        logger.exception("[MIGRATION_RUNNER] Migration failed:")

        # Cleanup on failure: rollback aborted transaction before attempting unlock
        if lock_acquired and "connection" in locals() and connection and not connection.closed:
            try:
                if connection.in_transaction():
                    connection.rollback()
            except Exception as rb_ex:  # noqa: BLE001
                logger.warning(f"[MIGRATION_RUNNER] Failure rollback failed: {rb_ex}")

            if not connection.invalidated:
                try:
                    unl_res = connection.execute(
                        text("SELECT pg_advisory_unlock(:lock_id);"),
                        {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
                    ).fetchone()
                    if unl_res and unl_res[0]:
                        logger.info(
                            f"[MIGRATION_RUNNER] Session advisory lock ({MIGRATION_ADVISORY_LOCK_ID}) released after failure rollback."
                        )
                        if connection.in_transaction():
                            connection.commit()
                except Exception as unl_ex:  # noqa: BLE001
                    logger.warning(f"[MIGRATION_RUNNER] Failure advisory unlock query failed: {unl_ex}")

        raise MigrationRunnerError(f"Migration execution failed: {redact_text(str(e))}") from e
    finally:
        if engine:
            engine.dispose()
        safe_close_connector(connector)
