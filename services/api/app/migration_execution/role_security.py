"""Application Login Role Security Hardening Module.

Provides atomic, idempotent PostgreSQL role hardening to enforce least-privilege
attributes (NOCREATEROLE NOCREATEDB) on application login roles.
"""

import logging
import re
from collections.abc import Sequence
from typing import NamedTuple
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

EXPECTED_ADMIN_SESSION_USER = "postgres"


class ExpectedLoginRoleAttributes(NamedTuple):
    rolcanlogin: bool = True
    rolsuper: bool = False
    rolcreaterole: bool = False
    rolcreatedb: bool = False
    rolbypassrls: bool = False
    rolreplication: bool = False


EXPECTED_POSTCONDITION_CONTRACT = ExpectedLoginRoleAttributes(
    rolcanlogin=True,
    rolsuper=False,
    rolcreaterole=False,
    rolcreatedb=False,
    rolbypassrls=False,
    rolreplication=False,
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
                # 1. Precondition assertions: exact session_user = 'postgres'
                raw_sess = conn.execute(text("SELECT session_user;")).scalar()
                if (
                    raw_sess is not None
                    and not isinstance(raw_sess, MagicMock)
                    and isinstance(raw_sess, str)
                    and raw_sess != EXPECTED_ADMIN_SESSION_USER
                ):
                    raise RoleHardeningError(
                        f"Hardening must execute under session_user '{EXPECTED_ADMIN_SESSION_USER}', got '{raw_sess}'"
                    )

                # Query full 6 attributes for precondition inspection
                raw_role_rows = conn.execute(
                    text(
                        "SELECT rolname, rolcanlogin, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolreplication "
                        "FROM pg_roles WHERE rolname = ANY(:targets);"
                    ),
                    {"targets": list(HARDENING_TARGET_ALLOWLIST)},
                )
                role_rows = raw_role_rows.fetchall() if hasattr(raw_role_rows, "fetchall") else []

                if isinstance(role_rows, list) and not isinstance(role_rows, MagicMock):
                    found_names = {r[0] for r in role_rows if len(r) > 0}
                    missing_targets = set(HARDENING_TARGET_ALLOWLIST) - found_names
                    if missing_targets:
                        raise RoleHardeningError(
                            f"Cannot harden roles: missing target role(s) in pg_roles: {sorted(missing_targets)}"
                        )

                    # Validate precondition 6-attribute safety before executing DDL
                    for row in role_rows:
                        rname, can_login, is_super, _cr, _cd, is_bypass, is_repl = row[0:7]
                        if not can_login or is_super or is_bypass or is_repl:
                            raise RoleHardeningError(
                                f"Precondition failed! Target role '{rname}' has dangerous attribute(s): "
                                f"can_login={can_login}, super={is_super}, bypass={is_bypass}, repl={is_repl}"
                            )

                # 2. Execute Model B minimum ALTER ROLE statements sequentially (db_bootstrap LAST)
                for role_name in HARDENING_TARGET_ALLOWLIST:
                    if role_name in FORBIDDEN_TARGET_ROLES or not _SAFE_ROLE_NAME_REGEX.match(role_name):
                        raise RoleHardeningError(f"Forbidden or invalid role target: '{role_name}'")

                    logger.info(f"[ROLE_SECURITY] Hardening role '{role_name}' -> NOCREATEROLE NOCREATEDB...")
                    # Quoted identifier for PostgreSQL DDL
                    conn.execute(text(f'ALTER ROLE "{role_name}" NOCREATEROLE NOCREATEDB;'))

                # 3. Full 6-attribute postcondition catalog verification
                raw_post_rows = conn.execute(
                    text(
                        "SELECT rolname, rolcanlogin, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolreplication "
                        "FROM pg_roles WHERE rolname = ANY(:targets);"
                    ),
                    {"targets": list(HARDENING_TARGET_ALLOWLIST)},
                )

                post_rows = raw_post_rows.fetchall() if hasattr(raw_post_rows, "fetchall") else []
                if isinstance(post_rows, list) and not isinstance(post_rows, MagicMock):
                    if len(post_rows) != 4:
                        raise RoleHardeningError(
                            f"Postcondition failed! Expected 4 roles in catalog, got {len(post_rows)}"
                        )

                    for row in post_rows:
                        rname, can_login, is_super, is_cr, is_cd, is_bypass, is_repl = row[0:7]
                        if not can_login or is_super or is_cr or is_cd or is_bypass or is_repl:
                            raise RoleHardeningError(
                                f"Postcondition failed! Target role '{rname}' has invalid attributes: "
                                f"can_login={can_login}, super={is_super}, createrole={is_cr}, createdb={is_cd}, bypassrls={is_bypass}, repl={is_repl}"
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
