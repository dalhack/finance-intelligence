"""Module for Bounded PostgreSQL Role Membership Attribute Remediation."""

import logging

from app.migration_execution.config import MigrationExecutionConfig
from app.migration_execution.provisioning import get_cloudsql_engine
from app.migration_execution.redaction import redact_text, safe_close_connector
from sqlalchemy import text
from sqlalchemy.engine import Engine

try:
    from google.cloud.sql.connector import Connector
except ImportError:
    Connector = None  # type: ignore[assignment,misc]

logger = logging.getLogger("migration_runner")


class RoleRemediationError(Exception):
    """Raised when role membership attribute remediation fails."""


def reconcile_role_membership_attributes(config: MigrationExecutionConfig) -> None:
    """Safely revokes ADMIN OPTION from db_owner on db_analysis_claim_owner role.

    Contract:
    - Target Granted Role: db_analysis_claim_owner
    - Target Member Role: db_owner
    - Expected Before Membership: present (admin_option=True)
    - Expected After Membership: present (admin_option=False)
    - Single transaction execution plane.
    """
    logger.info("[ROLE_REMEDIATION] Starting role membership attribute reconciliation...")

    if not config.initial_admin_password:
        raise RoleRemediationError("INITIAL_ADMIN_PASSWORD is required for role attribute remediation.")

    sys_engine: Engine | None = None
    sys_connector: Connector | None = None

    try:
        sys_engine, sys_connector = get_cloudsql_engine(
            config,
            user="postgres",
            password=config.initial_admin_password,
            database=config.target_database,
            autocommit=False,
        )

        with sys_engine.connect() as conn, conn.begin():
            # Query before-state
            res = conn.execute(
                text(
                    "SELECT m.admin_option "
                    "FROM pg_auth_members m "
                    "JOIN pg_roles r_granted ON m.roleid = r_granted.oid "
                    "JOIN pg_roles r_member ON m.member = r_member.oid "
                    "WHERE r_granted.rolname = 'db_analysis_claim_owner' AND r_member.rolname = 'db_owner'"
                )
            ).fetchone()

            if not res:
                raise RoleRemediationError(
                    "Before-state check failed: 'db_owner' is not a member of 'db_analysis_claim_owner'."
                )

            admin_before = bool(res[0])
            logger.info(f"[ROLE_REMEDIATION] Before-state admin_option on 'db_owner': {admin_before}")

            if admin_before:
                logger.info("[ROLE_REMEDIATION] Revoking ADMIN OPTION for db_analysis_claim_owner from db_owner...")
                conn.execute(text("REVOKE ADMIN OPTION FOR db_analysis_claim_owner FROM db_owner;"))
            else:
                logger.info("[ROLE_REMEDIATION] NO-OP: admin_option is already False.")

            # Query after-state verification
            after_res = conn.execute(
                text(
                    "SELECT m.admin_option "
                    "FROM pg_auth_members m "
                    "JOIN pg_roles r_granted ON m.roleid = r_granted.oid "
                    "JOIN pg_roles r_member ON m.member = r_member.oid "
                    "WHERE r_granted.rolname = 'db_analysis_claim_owner' AND r_member.rolname = 'db_owner'"
                )
            ).fetchone()

            if not after_res:
                raise RoleRemediationError(
                    "After-state verification failed: Membership 'db_owner' in 'db_analysis_claim_owner' was lost!"
                )

            admin_after = bool(after_res[0])
            if admin_after:
                raise RoleRemediationError("After-state verification failed: admin_option is still True after REVOKE!")

            # Verify no reverse membership (db_owner granted to db_analysis_claim_owner)
            reverse_res = conn.execute(
                text(
                    "SELECT 1 FROM pg_auth_members m "
                    "JOIN pg_roles r_granted ON m.roleid = r_granted.oid "
                    "JOIN pg_roles r_member ON m.member = r_member.oid "
                    "WHERE r_granted.rolname = 'db_owner' AND r_member.rolname = 'db_analysis_claim_owner'"
                )
            ).scalar()

            if reverse_res:
                raise RoleRemediationError(
                    "After-state verification failed: Reverse membership 'db_owner' -> 'db_analysis_claim_owner' detected!"
                )

            logger.info(
                "[ROLE_REMEDIATION] SUCCESS: Membership retained (admin_option=False, reverse_membership=absent)."
            )

    except Exception as e:
        logger.error(f"[ROLE_REMEDIATION] Reconciliation failed: {redact_text(str(e))}")
        raise RoleRemediationError(f"Role attribute remediation failed: {redact_text(str(e))}") from e
    finally:
        if sys_engine:
            sys_engine.dispose()
        if sys_connector:
            safe_close_connector(sys_connector)
