"""Integration tests for role hardening against real PostgreSQL database."""

import os

import pytest
from app.migration_execution.role_security import (
    HARDENING_TARGET_ALLOWLIST,
    harden_application_login_roles,
)
from sqlalchemy import create_engine, text

POSTGRES_TEST_DSN = os.environ.get("POSTGRES_TEST_DSN")


@pytest.fixture
def pg_elevated_roles():
    """Fixture that sets up elevated CREATEROLE CREATEDB attributes on target login roles."""
    if not POSTGRES_TEST_DSN:
        pytest.skip("POSTGRES_TEST_DSN not set")

    engine = create_engine(POSTGRES_TEST_DSN)
    with engine.connect() as conn, conn.begin():
        # Ensure target login roles exist
        for role in HARDENING_TARGET_ALLOWLIST:
            res = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role;"), {"role": role}).scalar()
            if not res:
                conn.execute(text(f'CREATE ROLE "{role}" WITH LOGIN CREATEROLE CREATEDB;'))
            else:
                conn.execute(text(f'ALTER ROLE "{role}" WITH CREATEROLE CREATEDB;'))

        # Ensure db_owner exists and db_bootstrap is member
        res_owner = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = 'db_owner';")).scalar()
        if not res_owner:
            conn.execute(text("CREATE ROLE db_owner WITH NOLOGIN;"))

        conn.execute(text("GRANT db_owner TO db_bootstrap;"))

    yield engine
    engine.dispose()


@pytest.mark.skipif(not POSTGRES_TEST_DSN, reason="POSTGRES_TEST_DSN not set")
def test_postgres_role_hardening_execution(pg_elevated_roles):
    """Integration test: Harden application login roles on PostgreSQL 16 and verify exact postconditions."""
    engine = pg_elevated_roles

    # 1. Run role security hardening
    harden_application_login_roles(engine)

    # 2. Verify physical visibility via independent connection
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT rolname, rolcanlogin, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolreplication "
                "FROM pg_roles WHERE rolname = ANY(:targets);"
            ),
            {"targets": list(HARDENING_TARGET_ALLOWLIST)},
        ).fetchall()

        assert len(rows) == 4
        for rname, canlogin, is_super, is_createrole, is_createdb, is_bypassrls, is_repl in rows:
            assert canlogin is True, f"Role '{rname}' lost LOGIN privilege"
            assert is_super is False, f"Role '{rname}' has SUPERUSER privilege"
            assert is_createrole is False, f"Role '{rname}' still has CREATEROLE privilege"
            assert is_createdb is False, f"Role '{rname}' still has CREATEDB privilege"
            assert is_bypassrls is False, f"Role '{rname}' has BYPASSRLS privilege"
            assert is_repl is False, f"Role '{rname}' has REPLICATION privilege"

        # 3. Verify db_bootstrap membership in db_owner is preserved
        is_member = conn.execute(
            text(
                "SELECT 1 FROM pg_auth_members m "
                "JOIN pg_roles r1 ON m.roleid = r1.oid "
                "JOIN pg_roles r2 ON m.member = r2.oid "
                "WHERE r1.rolname = 'db_owner' AND r2.rolname = 'db_bootstrap';"
            )
        ).scalar()
        assert is_member == 1, "'db_bootstrap' lost membership in 'db_owner'"


@pytest.mark.skipif(not POSTGRES_TEST_DSN, reason="POSTGRES_TEST_DSN not set")
def test_postgres_role_hardening_idempotent(pg_elevated_roles):
    """Integration test: Hardening is 100% idempotent when run multiple times."""
    engine = pg_elevated_roles

    harden_application_login_roles(engine)
    harden_application_login_roles(engine)  # Second execution

    with engine.connect() as conn:
        elevated = conn.execute(
            text(
                "SELECT rolname FROM pg_roles WHERE rolname = ANY(:targets) AND (rolcreaterole = true OR rolcreatedb = true);"
            ),
            {"targets": list(HARDENING_TARGET_ALLOWLIST)},
        ).fetchall()
        assert len(elevated) == 0
