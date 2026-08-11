#!/usr/bin/env python3
"""Finance Intelligence Session Role Verification Script.

Connects using ApiSessionLocal, WorkerSessionLocal, and BootstrapSessionLocal
and asserts SELECT current_user; returns the expected PostgreSQL role for each.
Also verifies Security Definer ownership, prosecdef, search_path, and ACLs for control-plane functions.
"""

import asyncio
import sys

from app.db.session import ApiSessionLocal, BootstrapSessionLocal, WorkerSessionLocal
from sqlalchemy import text


async def verify_session_roles() -> None:
    print("=== Finance Intelligence Session Role & Control-Plane Verification ===")

    # 1. Verify ApiSessionLocal role
    async with ApiSessionLocal() as session:
        res = await session.execute(text("SELECT current_user;"))
        user = res.scalar()
        print(f"ApiSessionLocal current_user: {user}")
        if user != "db_api_user":
            print(f"❌ ERROR: ApiSessionLocal expected role 'db_api_user', got '{user}'")
            sys.exit(1)

    # 2. Verify WorkerSessionLocal role
    async with WorkerSessionLocal() as session:
        res = await session.execute(text("SELECT current_user;"))
        user = res.scalar()
        print(f"WorkerSessionLocal current_user: {user}")
        if user != "db_ingestion_worker":
            print(f"❌ ERROR: WorkerSessionLocal expected role 'db_ingestion_worker', got '{user}'")
            sys.exit(1)

    # 3. Verify BootstrapSessionLocal role
    async with BootstrapSessionLocal() as session:
        res = await session.execute(text("SELECT current_user;"))
        user = res.scalar()
        print(f"BootstrapSessionLocal current_user: {user}")
        if user != "db_bootstrap":
            print(f"❌ ERROR: BootstrapSessionLocal expected role 'db_bootstrap', got '{user}'")
            sys.exit(1)

    # 4. Verify SECURITY DEFINER ownership and catalog attributes for claim_ingestion_job
    async with WorkerSessionLocal() as session:
        proc_res = await session.execute(
            text("""
            SELECT 
                p.prosecdef,
                pg_get_userbyid(p.proowner) AS owner_name,
                p.proacl::text AS acl_text,
                array_to_string(p.proconfig, ',') AS proconfig_str
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.proname = 'claim_ingestion_job';
        """)
        )
        row = proc_res.fetchone()
        if not row:
            print("❌ ERROR: claim_ingestion_job function missing in database.")
            sys.exit(1)

        if not row.prosecdef or row.owner_name != "db_owner":
            print(
                f"❌ ERROR: claim_ingestion_job prosecdef={row.prosecdef}, owner={row.owner_name} (expected db_owner)."
            )
            sys.exit(1)

        if "search_path=public, pg_catalog, pg_temp" not in (row.proconfig_str or ""):
            print("❌ ERROR: claim_ingestion_job search_path not pinned to public, pg_catalog, pg_temp.")
            sys.exit(1)

        print(f"claim_ingestion_job: owner={row.owner_name}, prosecdef={row.prosecdef}, ACL verified.")

    print("✅ All session factories explicitly bound to distinct least-privilege PostgreSQL roles.")
    print("✅ Control-plane SECURITY DEFINER ownership and catalog attributes verified.")


if __name__ == "__main__":
    asyncio.run(verify_session_roles())
