import argparse
import asyncio
import os
import sys
from urllib.parse import urlparse
import asyncpg


def verify_ci_safety_guard(dsn: str) -> None:
    """CI Safety Guard: Prevents role provisioning script from executing against production databases."""
    parsed = urlparse(dsn)
    hostname = (parsed.hostname or "").lower()
    dbname = (parsed.path.lstrip("/") or "").lower()

    safe_hosts = {"localhost", "127.0.0.1", "postgres", "0.0.0.0"}
    is_safe_host = hostname in safe_hosts or "test" in hostname or "ci" in hostname or "dev" in hostname
    is_safe_db = "test" in dbname or "roundtrip" in dbname or "dev" in dbname or "ci" in dbname

    if "prod" in hostname or "production" in hostname or "prod" in dbname:
        print(f"SAFETY GUARD FAILURE: Target DB ({hostname}/{dbname}) is marked as PRODUCTION!", file=sys.stderr)
        sys.exit(1)

    if not (is_safe_host or is_safe_db):
        print(f"SAFETY GUARD FAILURE: Target DB ({hostname}/{dbname}) is not a recognized CI/test environment!", file=sys.stderr)
        sys.exit(1)


async def provision_ci_roles(dsn: str) -> None:
    verify_ci_safety_guard(dsn)

    # Convert asyncpg driver prefix if present
    connect_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = await asyncpg.connect(connect_dsn)
    except Exception as e:
        print(f"FAILED to connect to PostgreSQL at {connect_dsn}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        # 1. Idempotent Role Creation SQL Statements
        role_statements = [
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_app_user') THEN
                    CREATE ROLE db_app_user NOLOGIN NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
                ELSE
                    ALTER ROLE db_app_user NOLOGIN NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
                END IF;
            END
            $$;
            """,
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_bootstrap') THEN
                    CREATE ROLE db_bootstrap LOGIN PASSWORD 'bootstrap_pass';
                END IF;
            END
            $$;
            """,
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                    CREATE ROLE db_api_user LOGIN PASSWORD 'api_pass';
                END IF;
            END
            $$;
            """,
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                    CREATE ROLE db_ingestion_worker LOGIN PASSWORD 'worker_pass';
                END IF;
            END
            $$;
            """,
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_maintenance_worker') THEN
                    CREATE ROLE db_maintenance_worker LOGIN PASSWORD 'dev_maintenance_pass_123';
                END IF;
            END
            $$;
            """,
        ]

        for stmt in role_statements:
            await conn.execute(stmt)

        # 2. Database Catalog Verification
        app_user_info = await conn.fetchrow("SELECT rolname, rolcanlogin, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'db_app_user'")
        if not app_user_info:
            print("CRITICAL: Legacy compatibility role db_app_user was not created!", file=sys.stderr)
            sys.exit(1)

        if app_user_info["rolcanlogin"]:
            print("CRITICAL SECURITY VIOLATION: db_app_user has LOGIN capability!", file=sys.stderr)
            sys.exit(1)

        if app_user_info["rolsuper"] or app_user_info["rolbypassrls"]:
            print("CRITICAL SECURITY VIOLATION: db_app_user has SUPERUSER or BYPASSRLS capability!", file=sys.stderr)
            sys.exit(1)

        member_count = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_auth_members WHERE roleid = (SELECT oid FROM pg_roles WHERE rolname = 'db_app_user')"
        )
        if member_count > 0:
            print(f"CRITICAL SECURITY VIOLATION: db_app_user has {member_count} active members!", file=sys.stderr)
            sys.exit(1)

        print("SINGLE SOURCE CI ROLE PROVISIONING SUCCESSFUL!")
        print("Verified Catalog: db_app_user is NOLOGIN, NOBYPASSRLS, NOSUPERUSER with 0 members.")
        print("Verified Catalog: db_bootstrap, db_api_user, db_ingestion_worker, db_maintenance_worker ready.")

    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Canonical Single-Source CI Role Provisioning Tool")
    parser.add_argument(
        "--target-url",
        default=os.environ.get("DATABASE_URL", "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test"),
        help="Target PostgreSQL DSN URL",
    )
    args = parser.parse_args()
    asyncio.run(provision_ci_roles(args.target_url))


if __name__ == "__main__":
    main()
