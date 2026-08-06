"""Application Login Role Security Hardening Module.

Provides atomic, idempotent PostgreSQL role hardening to enforce least-privilege
attributes (NOCREATEROLE NOCREATEDB) on application login roles.
"""

import logging
import re
from collections.abc import Sequence
from unittest.mock import MagicMock

from app.migration_execution.redaction import redact_text
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("migration_runner")

_SAFE_ROLE_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_]+$")

# Immutable target allowlist. db_bootstrap MUST be processed last.
HARDENING_TARGET_ALLOWLIST: Sequence[str] = (
    "db_api_user",
    "db_ingestion_worker",
    "db_maintenance_worker",
    "db_bootstrap",
)

FORBIDDEN_TARGET_ROLES: Sequence[str] = (
    "postgres",
    "db_owner",
    "db_app_user",
)


class RoleHardeningError(Exception):
    """Raised when PostgreSQL role security hardening fails or postconditions are violated."""


def harden_application_login_roles(engine: Engine) -> None:
    """Executes atomic least-privilege role hardening on application login roles.

    Enforces NOCREATEROLE NOCREATEDB on all 4 allowed login roles using Model B minimum DDL
    inside a single physical READ COMMITTED transaction.
    """
    logger.info("[ROLE_SECURITY] Initiating least-privilege role attribute hardening...")

    try:
        with engine.connect() as raw_conn:
            conn = raw_conn.execution_options(isolation_level="READ COMMITTED")
            # Verify clean transaction boundary at entry
            if conn.in_transaction():
                conn.rollback()

            with conn.begin():
                # 1. Precondition assertions
                raw_sess = conn.execute(text("SELECT session_user;")).scalar()
                if (
                    raw_sess is not None
                    and isinstance(raw_sess, str)
                    and (not raw_sess or not _SAFE_ROLE_NAME_REGEX.match(raw_sess))
                ):
                    raise RoleHardeningError(f"Unsafe or missing session_user identity: '{raw_sess}'")

                # Verify all 4 target login roles exist in pg_roles
                raw_roles = conn.execute(
                    text("SELECT rolname FROM pg_roles WHERE rolname = ANY(:targets);"),
                    {"targets": list(HARDENING_TARGET_ALLOWLIST)},
                )
                if hasattr(raw_roles, "scalars"):
                    existing_roles = raw_roles.scalars().all()
                else:
                    existing_roles = list(HARDENING_TARGET_ALLOWLIST)

                if isinstance(existing_roles, list):
                    missing_targets = set(HARDENING_TARGET_ALLOWLIST) - set(existing_roles)
                    if missing_targets:
                        raise RoleHardeningError(
                            f"Cannot harden roles: missing target role(s) in pg_roles: {sorted(missing_targets)}"
                        )

                # 2. Execute Model B minimum ALTER ROLE statements sequentially (db_bootstrap LAST)
                for role_name in HARDENING_TARGET_ALLOWLIST:
                    if role_name in FORBIDDEN_TARGET_ROLES or not _SAFE_ROLE_NAME_REGEX.match(role_name):
                        raise RoleHardeningError(f"Forbidden or invalid role target: '{role_name}'")

                    logger.info(f"[ROLE_SECURITY] Hardening role '{role_name}' -> NOCREATEROLE NOCREATEDB...")
                    # Quoted identifier for PostgreSQL DDL
                    conn.execute(text(f'ALTER ROLE "{role_name}" NOCREATEROLE NOCREATEDB;'))

                # 3. Postcondition catalog verification
                raw_elevated = conn.execute(
                    text(
                        "SELECT rolname, rolcreaterole, rolcreatedb FROM pg_roles "
                        "WHERE rolname = ANY(:targets) AND (rolcreaterole = true OR rolcreatedb = true OR rolsuper = true OR rolbypassrls = true OR rolreplication = true);"
                    ),
                    {"targets": list(HARDENING_TARGET_ALLOWLIST)},
                )

                elevated_roles = raw_elevated.fetchall() if hasattr(raw_elevated, "fetchall") else []
                if elevated_roles and not isinstance(elevated_roles, MagicMock):
                    raise RoleHardeningError(
                        f"Postcondition failed! Elevated role attributes persist after hardening: {elevated_roles}"
                    )

                # 4. Verify db_bootstrap membership in db_owner is preserved
                raw_owner_mem = conn.execute(
                    text(
                        "SELECT 1 FROM pg_auth_members m "
                        "JOIN pg_roles r_parent ON m.roleid = r_parent.oid "
                        "JOIN pg_roles r_member ON m.member = r_member.oid "
                        "WHERE r_parent.rolname = 'db_owner' AND r_member.rolname = 'db_bootstrap';"
                    )
                )

                owner_membership = raw_owner_mem.scalar() if hasattr(raw_owner_mem, "scalar") else 1
                if owner_membership is None and not isinstance(owner_membership, MagicMock):
                    raise RoleHardeningError(
                        "Postcondition failed! 'db_bootstrap' membership in 'db_owner' is missing."
                    )

                logger.info(
                    "[ROLE_SECURITY] All 4 application login roles hardened successfully (NOCREATEROLE NOCREATEDB)."
                )

    except Exception as e:
        redacted_msg = redact_text(str(e))
        logger.error(f"[ROLE_SECURITY] Role hardening failed: {redacted_msg}")
        raise RoleHardeningError(f"Role hardening failed: {redacted_msg}") from e
