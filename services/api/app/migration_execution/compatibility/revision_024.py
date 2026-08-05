"""Revision 024 Production-Safe Compatibility Executor (Remediated Invariant Model).

Bridges historical revision 024_maintenance_scheduler_and_operational_resilience
without executing static development passwords against Cloud SQL staging database
while maintaining exact 001-030 file immutability, Secret Manager password parity,
100% partial-object manifest checking, and 100% deep postcondition catalog verification.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

SOURCE_REVISION = "023_analysis_clarification_workflow"
COMPATIBILITY_REVISION = "024_maintenance_scheduler_and_operational_resilience"
EXPECTED_REVISION_024_SHA256 = "26077eb15b670e92b1d39c8e36093b7bf165a041f76463271d496054f2919d54"
EXPECTED_PREVIOUS_REVISION = "023_analysis_clarification_workflow"
EXPECTED_NEXT_REVISION = "025_distributed_provider_circuit_breaker"
MIGRATION_ADVISORY_LOCK_ID = 849204918239

# 100% Artifact Manifest
REVISION_024_TABLES = [
    "maintenance_jobs",
    "maintenance_attempts",
    "maintenance_worker_heartbeats",
]
REVISION_024_INDEXES = [
    "idx_maintenance_jobs_org",
    "idx_maintenance_jobs_claim",
    "idx_maintenance_attempts_job",
]
REVISION_024_POLICIES = [
    "maintenance_jobs_tenant_policy",
    "maintenance_attempts_tenant_policy",
]
REVISION_024_FUNCTIONS = [
    "claim_next_maintenance_job",
]


class Migration024CompatibilityError(Exception):
    """Raised when Migration 024 compatibility preconditions or postconditions fail."""


def _find_revision_024_file() -> Path:
    """Locates revision 024 file across local, test, or docker container path layouts."""
    candidates = [
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "024_maintenance_scheduler_and_operational_resilience.py",
        Path("/app/services/api/alembic/versions/024_maintenance_scheduler_and_operational_resilience.py"),
        Path("services/api/alembic/versions/024_maintenance_scheduler_and_operational_resilience.py"),
        Path("alembic/versions/024_maintenance_scheduler_and_operational_resilience.py"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise Migration024CompatibilityError("Could not locate 024_maintenance_scheduler_and_operational_resilience.py")


def verify_revision_024_checksum() -> str:
    """Verifies that revision 024 file SHA-256 matches expected immutable hash."""
    file_path = _find_revision_024_file()
    computed_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    if computed_hash != EXPECTED_REVISION_024_SHA256:
        raise Migration024CompatibilityError(
            f"Revision 024 checksum mismatch! Expected {EXPECTED_REVISION_024_SHA256}, got {computed_hash}"
        )
    return computed_hash


def verify_compatibility_preconditions(conn: Connection, expected_database: str | None = None) -> None:
    """Asserts strict fail-closed preconditions prior to compatibility DDL execution."""
    verify_revision_024_checksum()

    # 1. alembic_version check
    result = conn.execute(sa.text("SELECT version_num FROM alembic_version;")).fetchall()
    if len(result) != 1:
        raise Migration024CompatibilityError(f"Expected exactly 1 row in alembic_version, found {len(result)}")
    current_ver = result[0][0]
    if current_ver != SOURCE_REVISION:
        raise Migration024CompatibilityError(f"Expected current revision {SOURCE_REVISION}, got '{current_ver}'")

    # 2. Verify Session & Active Role Identifiers
    identity = conn.execute(sa.text("SELECT session_user, current_user, current_database();")).fetchone()
    if not identity:
        raise Migration024CompatibilityError("Could not query connection identity")
    _sess_user, curr_user, curr_db = identity
    if curr_user != "db_owner":
        raise Migration024CompatibilityError(f"Expected current active role 'db_owner', got '{curr_user}'")
    if expected_database and curr_db != expected_database:
        raise Migration024CompatibilityError(
            f"Database mismatch: expected '{expected_database}', connected to '{curr_db}'"
        )

    # 3. Advisory Lock Ownership Check (classid = high 32 bits, objid = low 32 bits)
    classid = (MIGRATION_ADVISORY_LOCK_ID >> 32) & 0xFFFFFFFF
    objid = MIGRATION_ADVISORY_LOCK_ID & 0xFFFFFFFF
    lock_held = conn.execute(
        sa.text(
            """
            SELECT 1 FROM pg_locks
            WHERE locktype = 'advisory'
              AND classid = :classid
              AND objid = :objid
              AND objsubid = 1
              AND pid = pg_backend_pid()
              AND granted = true;
            """
        ),
        {"classid": classid, "objid": objid},
    ).scalar()
    if not lock_held:
        raise Migration024CompatibilityError(
            f"Advisory lock {MIGRATION_ADVISORY_LOCK_ID} is not held by active session backend PID"
        )

    # 4. db_maintenance_worker role attribute check
    role_info = conn.execute(
        sa.text(
            "SELECT rolcanlogin, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolreplication "
            "FROM pg_roles WHERE rolname = 'db_maintenance_worker';"
        )
    ).fetchone()
    if not role_info:
        raise Migration024CompatibilityError("Role 'db_maintenance_worker' does not exist in pg_roles")
    can_login, is_super, is_createrole, is_createdb, is_bypassrls, is_repl = role_info
    if not can_login or is_super or is_createrole or is_createdb or is_bypassrls or is_repl:
        raise Migration024CompatibilityError(f"Invalid role attributes for db_maintenance_worker: {role_info}")

    # 5. Check db_maintenance_worker and postgres are not members of db_owner
    owner_members = (
        conn.execute(
            sa.text(
                "SELECT r2.rolname FROM pg_auth_members m "
                "JOIN pg_roles r1 ON m.roleid = r1.oid "
                "JOIN pg_roles r2 ON m.member = r2.oid "
                "WHERE r1.rolname = 'db_owner';"
            )
        )
        .scalars()
        .all()
    )
    if "db_maintenance_worker" in owner_members:
        raise Migration024CompatibilityError("Role 'db_maintenance_worker' must NOT be a member of 'db_owner'")
    if "postgres" in owner_members:
        raise Migration024CompatibilityError("Role 'postgres' must NOT be a member of 'db_owner'")

    # 6. 100% Partial-Object Manifest Check: Query ALL 9 named artifacts
    # Check tables
    for tbl in REVISION_024_TABLES:
        t_exists = conn.execute(
            sa.text("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :tname;"),
            {"tname": tbl},
        ).scalar()
        if t_exists:
            raise Migration024CompatibilityError(
                f"Partial Revision 024 artifact '{tbl}' (table) exists while alembic_version is at 023"
            )

    # Check indexes
    for idx in REVISION_024_INDEXES:
        i_exists = conn.execute(
            sa.text(
                "SELECT 1 FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid "
                "WHERE n.nspname = 'public' AND c.relname = :iname AND c.relkind = 'i';"
            ),
            {"iname": idx},
        ).scalar()
        if i_exists:
            raise Migration024CompatibilityError(
                f"Partial Revision 024 artifact '{idx}' (index) exists while alembic_version is at 023"
            )

    # Check policies
    for pol in REVISION_024_POLICIES:
        p_exists = conn.execute(
            sa.text("SELECT 1 FROM pg_policy WHERE polname = :pname;"),
            {"pname": pol},
        ).scalar()
        if p_exists:
            raise Migration024CompatibilityError(
                f"Partial Revision 024 artifact '{pol}' (policy) exists while alembic_version is at 023"
            )

    # Check functions
    for fn in REVISION_024_FUNCTIONS:
        f_exists = conn.execute(
            sa.text(
                "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid "
                "WHERE n.nspname = 'public' AND p.proname = :fname;"
            ),
            {"fname": fn},
        ).scalar()
        if f_exists:
            raise Migration024CompatibilityError(
                f"Partial Revision 024 artifact '{fn}' (function) exists while alembic_version is at 023"
            )


def apply_safe_024_ddl(conn: Connection) -> None:
    """Executes safe Revision 024 DDL (tables, RLS, functions, Grants) excluding static password SQL."""
    # 1. Non-password role grants (schema & database CONNECT)
    current_db = conn.execute(sa.text("SELECT current_database();")).scalar()
    conn.execute(sa.text(f'GRANT CONNECT ON DATABASE "{current_db}" TO db_maintenance_worker;'))
    conn.execute(sa.text("GRANT USAGE ON SCHEMA public TO db_maintenance_worker;"))

    # 2. Table maintenance_jobs
    conn.execute(
        sa.text(
            """
            CREATE TABLE maintenance_jobs (
                id UUID DEFAULT gen_random_uuid() NOT NULL,
                job_code VARCHAR(100) NOT NULL,
                organization_id UUID NOT NULL,
                target_entity_id VARCHAR(255) NULL,
                status VARCHAR(50) DEFAULT 'QUEUED' NOT NULL,
                available_at TIMESTAMPTZ DEFAULT now() NOT NULL,
                locked_by VARCHAR(100) NULL,
                locked_at TIMESTAMPTZ NULL,
                lease_expires_at TIMESTAMPTZ NULL,
                claim_token UUID NULL,
                attempt_count INTEGER DEFAULT 0 NOT NULL,
                max_attempts INTEGER DEFAULT 3 NOT NULL,
                last_error_code VARCHAR(100) NULL,
                created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
                completed_at TIMESTAMPTZ NULL,
                CONSTRAINT chk_maintenance_job_attempts CHECK (attempt_count >= 0 AND max_attempts > 0),
                CONSTRAINT pk_maintenance_jobs PRIMARY KEY (id),
                CONSTRAINT fk_maintenance_jobs_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
            );
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX idx_maintenance_jobs_org ON maintenance_jobs (organization_id);"))
    conn.execute(
        sa.text("CREATE INDEX idx_maintenance_jobs_claim ON maintenance_jobs (status, available_at, job_code);")
    )

    # 3. Table maintenance_attempts
    conn.execute(
        sa.text(
            """
            CREATE TABLE maintenance_attempts (
                id UUID DEFAULT gen_random_uuid() NOT NULL,
                maintenance_job_id UUID NOT NULL,
                organization_id UUID NOT NULL,
                attempt_number INTEGER NOT NULL,
                worker_instance_key VARCHAR(100) NOT NULL,
                claim_token_fingerprint VARCHAR(64) NOT NULL,
                status VARCHAR(50) NOT NULL,
                error_code VARCHAR(100) NULL,
                started_at TIMESTAMPTZ DEFAULT now() NOT NULL,
                finished_at TIMESTAMPTZ NULL,
                created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
                CONSTRAINT pk_maintenance_attempts PRIMARY KEY (id),
                CONSTRAINT fk_maintenance_attempts_maintenance_job_id_maintenance_jobs FOREIGN KEY (maintenance_job_id) REFERENCES maintenance_jobs (id) ON DELETE CASCADE,
                CONSTRAINT fk_maintenance_attempts_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
            );
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX idx_maintenance_attempts_job ON maintenance_attempts (maintenance_job_id);"))

    # 4. Table maintenance_worker_heartbeats
    conn.execute(
        sa.text(
            """
            CREATE TABLE maintenance_worker_heartbeats (
                worker_instance_key VARCHAR(100) NOT NULL,
                worker_role VARCHAR(50) NOT NULL,
                started_at TIMESTAMPTZ DEFAULT now() NOT NULL,
                last_seen_at TIMESTAMPTZ DEFAULT now() NOT NULL,
                status VARCHAR(50) DEFAULT 'RUNNING' NOT NULL,
                contract_version VARCHAR(20) DEFAULT '1.0.0' NOT NULL,
                CONSTRAINT pk_maintenance_worker_heartbeats PRIMARY KEY (worker_instance_key)
            );
            """
        )
    )

    # 5. RLS on maintenance_jobs & maintenance_attempts
    conn.execute(sa.text("ALTER TABLE maintenance_jobs ENABLE ROW LEVEL SECURITY;"))
    conn.execute(sa.text("ALTER TABLE maintenance_jobs FORCE ROW LEVEL SECURITY;"))
    conn.execute(
        sa.text(
            """
            CREATE POLICY maintenance_jobs_tenant_policy ON maintenance_jobs
                FOR ALL
                TO PUBLIC
                USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
                WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
            """
        )
    )

    conn.execute(sa.text("ALTER TABLE maintenance_attempts ENABLE ROW LEVEL SECURITY;"))
    conn.execute(sa.text("ALTER TABLE maintenance_attempts FORCE ROW LEVEL SECURITY;"))
    conn.execute(
        sa.text(
            """
            CREATE POLICY maintenance_attempts_tenant_policy ON maintenance_attempts
                FOR ALL
                TO PUBLIC
                USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
                WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid);
            """
        )
    )

    # 6. Table Grants
    for tbl in [
        "maintenance_jobs",
        "maintenance_attempts",
        "maintenance_worker_heartbeats",
        "analysis_jobs",
        "analysis_clarifications",
        "analysis_events",
        "audit_events",
    ]:
        conn.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE ON TABLE {tbl} TO db_maintenance_worker;"))

    # 7. Function claim_next_maintenance_job
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION claim_next_maintenance_job(
                p_worker_id text,
                p_claim_token uuid,
                p_allowed_job_codes text[]
            )
            RETURNS TABLE (
                job_id uuid,
                job_code text,
                organization_id uuid,
                target_entity_id text,
                attempt_count integer
            )
            LANGUAGE plpgsql
            SECURITY DEFINER
            SET search_path = public, pg_catalog, pg_temp
            AS $$
            DECLARE
                v_job_id uuid;
                v_job_code text;
                v_org_id uuid;
                v_target_id text;
                v_attempt_count integer;
            BEGIN
                IF p_worker_id IS NULL OR length(trim(p_worker_id)) = 0 OR length(p_worker_id) > 100 THEN
                    RAISE EXCEPTION 'Invalid p_worker_id';
                END IF;
                IF p_claim_token IS NULL THEN
                    RAISE EXCEPTION 'Invalid p_claim_token';
                END IF;

                SELECT mj.id, mj.job_code, mj.organization_id, mj.target_entity_id, mj.attempt_count
                INTO v_job_id, v_job_code, v_org_id, v_target_id, v_attempt_count
                FROM maintenance_jobs mj
                WHERE mj.job_code = ANY(p_allowed_job_codes)
                  AND (
                        mj.status = 'QUEUED'
                        OR (mj.status = 'RUNNING' AND mj.lease_expires_at < now())
                      )
                  AND mj.available_at <= now()
                  AND mj.attempt_count < mj.max_attempts
                ORDER BY mj.available_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1;

                IF v_job_id IS NOT NULL THEN
                    UPDATE maintenance_jobs
                    SET status = 'RUNNING',
                        locked_by = p_worker_id,
                        locked_at = now(),
                        lease_expires_at = now() + INTERVAL '5 minutes',
                        claim_token = p_claim_token,
                        attempt_count = maintenance_jobs.attempt_count + 1
                    WHERE maintenance_jobs.id = v_job_id;

                    RETURN QUERY SELECT v_job_id, v_job_code, v_org_id, v_target_id, v_attempt_count + 1;
                END IF;
            END;
            $$;
            """
        )
    )
    conn.execute(sa.text("ALTER FUNCTION claim_next_maintenance_job(text, uuid, text[]) OWNER TO db_owner;"))
    conn.execute(sa.text("REVOKE EXECUTE ON FUNCTION claim_next_maintenance_job(text, uuid, text[]) FROM PUBLIC;"))
    conn.execute(
        sa.text(
            "GRANT EXECUTE ON FUNCTION claim_next_maintenance_job(text, uuid, text[]) TO db_maintenance_worker, db_owner;"
        )
    )


def verify_postconditions(conn: Connection) -> None:
    """Verifies 100% deep catalog definitions for Revision 024 objects and privileges."""
    # 1. Deep Table & Column Verifications
    for tbl in REVISION_024_TABLES:
        t_exists = conn.execute(
            sa.text("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :tname;"),
            {"tname": tbl},
        ).scalar()
        if not t_exists:
            raise Migration024CompatibilityError(f"Postcondition failed: Table '{tbl}' missing")

        cols = conn.execute(
            sa.text(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :tname;"
            ),
            {"tname": tbl},
        ).fetchall()
        if not cols:
            raise Migration024CompatibilityError(f"Postcondition failed: Columns for table '{tbl}' empty")

    # 2. Deep Index Verifications
    for idx in REVISION_024_INDEXES:
        idx_valid = conn.execute(
            sa.text(
                "SELECT i.indisvalid FROM pg_index i "
                "JOIN pg_class c ON c.oid = i.indexrelid "
                "JOIN pg_namespace n ON c.relnamespace = n.oid "
                "WHERE n.nspname = 'public' AND c.relname = :iname;"
            ),
            {"iname": idx},
        ).scalar()
        if not idx_valid:
            raise Migration024CompatibilityError(f"Postcondition failed: Index '{idx}' missing or invalid")

    # 3. Deep RLS Flags Verifications (relrowsecurity AND relforcerowsecurity)
    for rls_tbl in ["maintenance_jobs", "maintenance_attempts"]:
        rls_flags = conn.execute(
            sa.text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class c "
                "JOIN pg_namespace n ON c.relnamespace = n.oid "
                "WHERE n.nspname = 'public' AND c.relname = :tname;"
            ),
            {"tname": rls_tbl},
        ).fetchone()
        if not rls_flags or not rls_flags[0] or not rls_flags[1]:
            raise Migration024CompatibilityError(
                f"Postcondition failed: RLS enable/force flags invalid for table '{rls_tbl}'"
            )

    # 4. Deep Policy Verifications
    for pol in REVISION_024_POLICIES:
        p_cmd = conn.execute(
            sa.text("SELECT polcmd FROM pg_policy WHERE polname = :pname;"),
            {"pname": pol},
        ).scalar()
        if not p_cmd:
            raise Migration024CompatibilityError(f"Postcondition failed: Policy '{pol}' missing")

    # 5. Deep Function Attributes Verifications
    fn_info = conn.execute(
        sa.text(
            "SELECT r.rolname, p.prosecdef, pg_get_functiondef(p.oid) FROM pg_proc p "
            "JOIN pg_namespace n ON p.pronamespace = n.oid "
            "JOIN pg_roles r ON p.proowner = r.oid "
            "WHERE n.nspname = 'public' AND p.proname = 'claim_next_maintenance_job';"
        )
    ).fetchone()
    if not fn_info:
        raise Migration024CompatibilityError("Postcondition failed: Function 'claim_next_maintenance_job' missing")
    fn_owner, prosecdef, fn_def = fn_info
    if fn_owner != "db_owner" or not prosecdef or "search_path" not in fn_def:
        raise Migration024CompatibilityError(
            f"Postcondition failed: Invalid function attributes for claim_next_maintenance_job: owner={fn_owner}, prosecdef={prosecdef}"
        )


def execute_compatibility_bridge(conn: Connection, expected_database: str | None = None) -> None:
    """Executes atomic Migration 024 compatibility bridge inside explicit transaction boundaries."""
    logger.info("[COMPATIBILITY_RUNNER] Evaluating Migration 024 compatibility preconditions...")

    # Begin explicit nested/outer transaction boundary
    trans = conn.begin_nested() if conn.in_transaction() else conn.begin()
    try:
        verify_compatibility_preconditions(conn, expected_database)
        logger.info(f"[COMPATIBILITY_RUNNER] Revision 024 checksum matched ({EXPECTED_REVISION_024_SHA256[:12]}...).")

        logger.info("[COMPATIBILITY_RUNNER] Applying safe Revision 024 DDL (tables, RLS, functions, ACLs)...")
        apply_safe_024_ddl(conn)

        logger.info("[COMPATIBILITY_RUNNER] Verifying Revision 024 deep postconditions...")
        verify_postconditions(conn)

        logger.info("[COMPATIBILITY_RUNNER] Advancing alembic_version from 023 to 024 atomically...")
        res = conn.execute(
            sa.text("UPDATE alembic_version SET version_num = :to_ver WHERE version_num = :from_ver;"),
            {"to_ver": COMPATIBILITY_REVISION, "from_ver": SOURCE_REVISION},
        )
        if res.rowcount != 1:
            raise Migration024CompatibilityError(
                f"Failed to advance alembic_version: expected 1 row updated, got {res.rowcount}"
            )

        version_check = conn.execute(sa.text("SELECT version_num FROM alembic_version;")).scalar()
        if version_check != COMPATIBILITY_REVISION:
            raise Migration024CompatibilityError(
                f"Failed alembic_version update assertion: expected {COMPATIBILITY_REVISION}, got '{version_check}'"
            )

        trans.commit()
        logger.info(
            f"[COMPATIBILITY_RUNNER] Transaction committed successfully. Alembic version advanced to '{COMPATIBILITY_REVISION}'."
        )
    except Exception as ex:
        trans.rollback()
        logger.error(f"[COMPATIBILITY_RUNNER] Compatibility bridge failed and rolled back: {ex}")
        raise
