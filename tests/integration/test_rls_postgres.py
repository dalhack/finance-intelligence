import os
from uuid import uuid4

import asyncpg
import pytest

RAW_OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL")
RAW_BOOTSTRAP_URL = os.environ.get("TEST_BOOTSTRAP_DATABASE_URL")
RAW_API_USER_URL = os.environ.get("TEST_API_DATABASE_URL")

OWNER_URL = RAW_OWNER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_OWNER_URL else None
BOOTSTRAP_URL = RAW_BOOTSTRAP_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_BOOTSTRAP_URL else None
API_USER_URL = RAW_API_USER_URL.replace("postgresql+asyncpg://", "postgresql://") if RAW_API_USER_URL else None

pytestmark = [pytest.mark.integration]


async def seed_tenant_data(conn: asyncpg.Connection, org_id: str, user_id: str, mem_id: str | None = None):
    await conn.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1, $2, $3);", org_id, f"Org {org_id}", f"org-{org_id}"
    )
    await conn.execute(
        "INSERT INTO users (id, external_subject, display_name) VALUES ($1, $2, $3);",
        user_id,
        f"sub-{user_id}",
        f"User {user_id}",
    )

    if mem_id:
        await conn.execute("SELECT set_config('app.current_organization_id', $1, true);", str(org_id))
        await conn.execute(
            "INSERT INTO memberships (id, user_id, organization_id) VALUES ($1, $2, $3);", mem_id, user_id, org_id
        )
        await conn.execute("SELECT set_config('app.current_organization_id', '', true);")


@pytest.mark.asyncio
async def test_migration_applies_cleanly():
    conn = await asyncpg.connect(OWNER_URL)
    row = await conn.fetchrow("SELECT version_num FROM alembic_version;")
    await conn.close()
    assert row is not None
    assert row["version_num"] in [
        "023_analysis_clarification_workflow",
        "024_maintenance_scheduler_and_operational_resilience",
        "025_distributed_provider_circuit_breaker",
        "026_public_schema_acl_hardening",
    ]


@pytest.mark.asyncio
async def test_runtime_role_privileges_and_force_rls():
    conn = await asyncpg.connect(OWNER_URL)
    role_row = await conn.fetchrow("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'db_api_user';")
    assert role_row is not None
    assert role_row["rolbypassrls"] is False, "CRITICAL: db_api_user MUST NOT possess BYPASSRLS privilege."

    for tbl in ["organizations", "users", "memberships", "membership_roles", "audit_events"]:
        class_row = await conn.fetchrow(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = $1;", tbl
        )
        assert class_row is not None
        assert class_row["relrowsecurity"] is True, f"Table {tbl} MUST have RLS enabled."
        assert class_row["relforcerowsecurity"] is True, f"Table {tbl} MUST have FORCE RLS enabled."

    await conn.close()


@pytest.mark.asyncio
async def test_lookup_user_membership_function_owner_and_acl_attributes():
    owner_conn = await asyncpg.connect(OWNER_URL)
    func_row = await owner_conn.fetchrow("""
        SELECT
            p.prosecdef,
            pg_get_userbyid(p.proowner) AS owner_name,
            p.proacl::text AS acl_text,
            has_function_privilege('db_bootstrap', p.oid, 'EXECUTE') AS bootstrap_can_execute
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'lookup_user_membership';
    """)
    await owner_conn.close()

    assert func_row is not None
    assert func_row["prosecdef"] is True, "Function MUST be defined with SECURITY DEFINER."
    assert func_row["owner_name"] == "db_owner", "Function owner MUST be db_owner."
    assert "db_bootstrap=X" not in str(func_row["acl_text"])
    assert func_row["bootstrap_can_execute"] is False, "db_bootstrap MUST NOT possess runtime EXECUTE privilege."


@pytest.mark.asyncio
async def test_tenant_a_sees_own_membership():
    owner_conn = await asyncpg.connect(OWNER_URL)
    org_a, user_a, mem_a = uuid4(), uuid4(), uuid4()
    await seed_tenant_data(owner_conn, org_a, user_a, mem_a)
    await owner_conn.close()

    api_conn = await asyncpg.connect(API_USER_URL)
    tr = api_conn.transaction()
    await tr.start()
    await api_conn.execute("SELECT set_config('app.current_organization_id', $1, true);", str(org_a))
    rows = await api_conn.fetch("SELECT * FROM memberships WHERE organization_id = $1;", org_a)
    await tr.rollback()
    await api_conn.close()

    assert len(rows) == 1
    assert rows[0]["id"] == mem_a


@pytest.mark.asyncio
async def test_tenant_a_cannot_see_tenant_b_membership():
    owner_conn = await asyncpg.connect(OWNER_URL)
    org_a, user_a, mem_a = uuid4(), uuid4(), uuid4()
    org_b, user_b, mem_b = uuid4(), uuid4(), uuid4()

    await seed_tenant_data(owner_conn, org_a, user_a, mem_a)
    await seed_tenant_data(owner_conn, org_b, user_b, mem_b)
    await owner_conn.close()

    api_conn = await asyncpg.connect(API_USER_URL)
    tr = api_conn.transaction()
    await tr.start()
    await api_conn.execute("SELECT set_config('app.current_organization_id', $1, true);", str(org_a))

    row_b = await api_conn.fetchrow("SELECT * FROM memberships WHERE id = $1;", mem_b)
    all_rows = await api_conn.fetch("SELECT * FROM memberships;")

    await tr.rollback()
    await api_conn.close()

    assert row_b is None, "Tenant A MUST NOT be able to read Tenant B's membership by ID."
    assert len(all_rows) == 1, "Tenant A query without filter MUST only return Tenant A's memberships."
    assert all_rows[0]["id"] == mem_a


@pytest.mark.asyncio
async def test_tenant_a_cannot_see_tenant_b_organization_metadata():
    owner_conn = await asyncpg.connect(OWNER_URL)
    org_a, user_a, mem_a = uuid4(), uuid4(), uuid4()
    org_b, user_b, mem_b = uuid4(), uuid4(), uuid4()

    await seed_tenant_data(owner_conn, org_a, user_a, mem_a)
    await seed_tenant_data(owner_conn, org_b, user_b, mem_b)
    await owner_conn.close()

    api_conn = await asyncpg.connect(API_USER_URL)
    tr = api_conn.transaction()
    await tr.start()
    await api_conn.execute("SELECT set_config('app.current_organization_id', $1, true);", str(org_a))

    org_b_row = await api_conn.fetchrow("SELECT * FROM organizations WHERE id = $1;", org_b)
    all_orgs = await api_conn.fetch("SELECT * FROM organizations;")

    await tr.rollback()
    await api_conn.close()

    assert org_b_row is None, "Tenant A MUST NOT see Tenant B's organization record."
    assert len(all_orgs) == 1
    assert all_orgs[0]["id"] == org_a


@pytest.mark.asyncio
async def test_tenant_a_cannot_see_tenant_b_user_metadata():
    owner_conn = await asyncpg.connect(OWNER_URL)
    org_a, user_a, mem_a = uuid4(), uuid4(), uuid4()
    org_b, user_b, mem_b = uuid4(), uuid4(), uuid4()

    await seed_tenant_data(owner_conn, org_a, user_a, mem_a)
    await seed_tenant_data(owner_conn, org_b, user_b, mem_b)
    await owner_conn.close()

    api_conn = await asyncpg.connect(API_USER_URL)
    tr = api_conn.transaction()
    await tr.start()
    await api_conn.execute("SELECT set_config('app.current_organization_id', $1, true);", str(org_a))

    user_b_row = await api_conn.fetchrow("SELECT * FROM users WHERE id = $1;", user_b)
    all_users = await api_conn.fetch("SELECT * FROM users;")

    await tr.rollback()
    await api_conn.close()

    assert user_b_row is None, "Tenant A MUST NOT see Tenant B's user metadata."
    assert len(all_users) == 1
    assert all_users[0]["id"] == user_a


@pytest.mark.asyncio
async def test_tenant_a_cannot_insert_membership_for_tenant_b():
    owner_conn = await asyncpg.connect(OWNER_URL)
    org_a, user_a = uuid4(), uuid4()
    org_b, user_b = uuid4(), uuid4()

    await seed_tenant_data(owner_conn, org_a, user_a)
    await seed_tenant_data(owner_conn, org_b, user_b)
    await owner_conn.close()

    api_conn = await asyncpg.connect(API_USER_URL)
    tr = api_conn.transaction()
    await tr.start()
    await api_conn.execute("SELECT set_config('app.current_organization_id', $1, true);", str(org_a))

    illegal_mem_id = uuid4()
    with pytest.raises(
        (asyncpg.exceptions.WithCheckOptionViolationError, asyncpg.exceptions.InsufficientPrivilegeError)
    ):
        await api_conn.execute(
            "INSERT INTO memberships (id, user_id, organization_id) VALUES ($1, $2, $3);",
            illegal_mem_id,
            user_a,
            org_b,
        )

    await tr.rollback()
    await api_conn.close()


@pytest.mark.asyncio
async def test_tenant_a_cannot_update_tenant_b_membership():
    owner_conn = await asyncpg.connect(OWNER_URL)
    org_a, user_a, mem_a = uuid4(), uuid4(), uuid4()
    org_b, user_b, mem_b = uuid4(), uuid4(), uuid4()

    await seed_tenant_data(owner_conn, org_a, user_a, mem_a)
    await seed_tenant_data(owner_conn, org_b, user_b, mem_b)
    await owner_conn.close()

    api_conn = await asyncpg.connect(API_USER_URL)
    tr = api_conn.transaction()
    await tr.start()
    await api_conn.execute("SELECT set_config('app.current_organization_id', $1, true);", str(org_a))

    res = await api_conn.execute("UPDATE memberships SET organization_id = $1 WHERE id = $2;", org_a, mem_b)

    await tr.rollback()
    await api_conn.close()

    assert res == "UPDATE 0", "Updating Tenant B's membership from Tenant A context MUST affect 0 rows."


@pytest.mark.asyncio
async def test_tenant_a_cannot_see_tenant_b_audit_events():
    owner_conn = await asyncpg.connect(OWNER_URL)
    org_a, user_a = uuid4(), uuid4()
    org_b, user_b = uuid4(), uuid4()

    await seed_tenant_data(owner_conn, org_a, user_a)
    await seed_tenant_data(owner_conn, org_b, user_b)

    event_a_id, event_b_id = uuid4(), uuid4()
    await owner_conn.execute(
        "INSERT INTO audit_events (id, organization_id, user_hash, org_hash, event_type, payload_summary, previous_hash, current_hash) VALUES ($1, $2, $3, $4, $5, $6, $7, $8);",
        event_a_id,
        org_a,
        "uhash_a",
        "ohash_a",
        "TEST_EVENT",
        '{"meta": "a"}',
        "0000",
        "1111",
    )
    await owner_conn.execute(
        "INSERT INTO audit_events (id, organization_id, user_hash, org_hash, event_type, payload_summary, previous_hash, current_hash) VALUES ($1, $2, $3, $4, $5, $6, $7, $8);",
        event_b_id,
        org_b,
        "uhash_b",
        "ohash_b",
        "TEST_EVENT",
        '{"meta": "b"}',
        "0000",
        "2222",
    )
    await owner_conn.close()

    api_conn = await asyncpg.connect(API_USER_URL)
    tr = api_conn.transaction()
    await tr.start()
    await api_conn.execute("SELECT set_config('app.current_organization_id', $1, true);", str(org_a))

    event_b_row = await api_conn.fetchrow("SELECT * FROM audit_events WHERE id = $1;", event_b_id)
    all_events = await api_conn.fetch("SELECT * FROM audit_events;")

    await tr.rollback()
    await api_conn.close()

    assert event_b_row is None, "Tenant A MUST NOT see Tenant B's audit events."
    assert len(all_events) == 1
    assert all_events[0]["id"] == event_a_id


@pytest.mark.asyncio
async def test_tenant_a_cannot_insert_audit_event_for_tenant_b():
    owner_conn = await asyncpg.connect(OWNER_URL)
    org_a, user_a = uuid4(), uuid4()
    org_b, user_b = uuid4(), uuid4()

    await seed_tenant_data(owner_conn, org_a, user_a)
    await seed_tenant_data(owner_conn, org_b, user_b)
    await owner_conn.close()

    api_conn = await asyncpg.connect(API_USER_URL)
    tr = api_conn.transaction()
    await tr.start()
    await api_conn.execute("SELECT set_config('app.current_organization_id', $1, true);", str(org_a))

    illegal_event_id = uuid4()
    with pytest.raises(
        (asyncpg.exceptions.WithCheckOptionViolationError, asyncpg.exceptions.InsufficientPrivilegeError)
    ):
        await api_conn.execute(
            "INSERT INTO audit_events (id, organization_id, user_hash, org_hash, event_type, payload_summary, previous_hash, current_hash) VALUES ($1, $2, $3, $4, $5, $6, $7, $8);",
            illegal_event_id,
            org_b,
            "uhash",
            "ohash",
            "ILLEGAL_INSERT",
            "{}",
            "0000",
            "9999",
        )

    await tr.rollback()
    await api_conn.close()


@pytest.mark.asyncio
async def test_api_user_cannot_update_audit_events():
    owner_conn = await asyncpg.connect(OWNER_URL)
    org_a, user_a = uuid4(), uuid4()
    await seed_tenant_data(owner_conn, org_a, user_a)

    event_id = uuid4()
    await owner_conn.execute(
        "INSERT INTO audit_events (id, organization_id, user_hash, org_hash, event_type, payload_summary, previous_hash, current_hash) VALUES ($1, $2, $3, $4, $5, $6, $7, $8);",
        event_id,
        org_a,
        "uhash",
        "ohash",
        "ORIGINAL_EVENT",
        "{}",
        "0000",
        "1111",
    )
    await owner_conn.close()

    api_conn = await asyncpg.connect(API_USER_URL)
    tr = api_conn.transaction()
    await tr.start()
    await api_conn.execute("SELECT set_config('app.current_organization_id', $1, true);", str(org_a))

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        await api_conn.execute("UPDATE audit_events SET event_type = 'TAMPERED' WHERE id = $1;", event_id)

    await tr.rollback()
    await api_conn.close()


@pytest.mark.asyncio
async def test_api_user_cannot_delete_audit_events():
    owner_conn = await asyncpg.connect(OWNER_URL)
    org_a, user_a = uuid4(), uuid4()
    await seed_tenant_data(owner_conn, org_a, user_a)

    event_id = uuid4()
    await owner_conn.execute(
        "INSERT INTO audit_events (id, organization_id, user_hash, org_hash, event_type, payload_summary, previous_hash, current_hash) VALUES ($1, $2, $3, $4, $5, $6, $7, $8);",
        event_id,
        org_a,
        "uhash",
        "ohash",
        "ORIGINAL_EVENT",
        "{}",
        "0000",
        "1111",
    )
    await owner_conn.close()

    api_conn = await asyncpg.connect(API_USER_URL)
    tr = api_conn.transaction()
    await tr.start()
    await api_conn.execute("SELECT set_config('app.current_organization_id', $1, true);", str(org_a))

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        await api_conn.execute("DELETE FROM audit_events WHERE id = $1;", event_id)

    await tr.rollback()
    await api_conn.close()


@pytest.mark.asyncio
async def test_missing_tenant_context_returns_zero_rows():
    owner_conn = await asyncpg.connect(OWNER_URL)
    org_a, user_a, mem_a = uuid4(), uuid4(), uuid4()
    await seed_tenant_data(owner_conn, org_a, user_a, mem_a)
    await owner_conn.close()

    api_conn = await asyncpg.connect(API_USER_URL)
    tr = api_conn.transaction()
    await tr.start()

    mem_rows = await api_conn.fetch("SELECT * FROM memberships;")
    org_rows = await api_conn.fetch("SELECT * FROM organizations;")
    user_rows = await api_conn.fetch("SELECT * FROM users;")

    await tr.rollback()
    await api_conn.close()

    assert len(mem_rows) == 0, "Query without app.current_organization_id MUST return 0 rows for memberships."
    assert len(org_rows) == 0, "Query without app.current_organization_id MUST return 0 rows for organizations."
    assert len(user_rows) == 0, "Query without app.current_organization_id MUST return 0 rows for users."


@pytest.mark.asyncio
async def test_all_public_functions_deny_public_and_app_user_execute():
    owner_conn = await asyncpg.connect(OWNER_URL)

    rows = await owner_conn.fetch("""
        SELECT 
            p.proname,
            has_function_privilege('public', p.oid, 'EXECUTE') as public_exec,
            has_function_privilege('db_app_user', p.oid, 'EXECUTE') as app_user_exec,
            has_function_privilege('db_bootstrap', p.oid, 'EXECUTE') as bootstrap_exec
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE n.nspname = 'public';
    """)

    failing_funcs = [r["proname"] for r in rows if r["public_exec"] or r["app_user_exec"] or r["bootstrap_exec"]]
    await owner_conn.close()

    assert len(failing_funcs) == 0, (
        f"SECURITY_VIOLATION: Functions retaining PUBLIC, db_app_user, or db_bootstrap EXECUTE: {failing_funcs}"
    )
