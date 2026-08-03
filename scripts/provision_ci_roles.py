import argparse
import asyncio
import os
import sys
from urllib.parse import urlparse
import asyncpg


def sanitize_connection_error(error_msg: str) -> str:
    """Strip sensitive information like passwords, usernames, and DSNs from error messages."""
    return "CI_ROLE_PROVISIONING_CONNECTION_FAILED: Connection to target database failed."


def verify_ci_target_allowlist(dsn: str, allow_local: bool = False) -> None:
    """Enforces strict target allowlist and CI execution marker."""

    # 1. CI Execution Marker Guard
    is_ci = os.environ.get("CI", "").lower() == "true" or os.environ.get("CONTINUOUS_INTEGRATION", "").lower() == "true"
    if not (is_ci or allow_local):
        print("ERROR: CI_ROLE_PROVISIONING_CI_MARKER_REQUIRED: CI environment marker required.", file=sys.stderr)
        sys.exit(1)

    # 2. Parse DSN safely
    clean_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    try:
        parsed = urlparse(clean_dsn)
    except Exception:
        print("ERROR: CI_ROLE_PROVISIONING_INVALID_DSN: Could not parse target DSN.", file=sys.stderr)
        sys.exit(1)

    hostname = (parsed.hostname or "").lower()
    dbname = (parsed.path.lstrip("/") or "").lower()

    # 3. Production Target Ban
    if "prod" in hostname or "production" in hostname or "prod" in dbname or "production" in dbname:
        print("ERROR: CI_ROLE_PROVISIONING_PRODUCTION_TARGET_FORBIDDEN: Target is marked as production.", file=sys.stderr)
        sys.exit(1)

    # 4. Strict Loopback / Service-Container Allowlist
    safe_hosts = {"localhost", "127.0.0.1", "postgres", "0.0.0.0"}
    is_safe_host = hostname in safe_hosts
    is_safe_db = "test" in dbname or "roundtrip" in dbname or "ci" in dbname

    if not (is_safe_host and is_safe_db):
        print(f"ERROR: CI_ROLE_PROVISIONING_TARGET_NOT_ALLOWED: Target DB ({hostname}/{dbname}) not in CI allowlist.", file=sys.stderr)
        sys.exit(1)


async def provision_ci_roles(dsn: str, allow_local: bool = False) -> None:
    verify_ci_target_allowlist(dsn, allow_local)

    connect_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

    # Ephemeral non-production test credentials from environment contracts
    bootstrap_pass = os.environ.get("TEST_BOOTSTRAP_PASSWORD", "bootstrap_pass")
    api_pass = os.environ.get("TEST_API_PASSWORD", "api_pass")
    worker_pass = os.environ.get("TEST_WORKER_PASSWORD", "worker_pass")
    maint_pass = os.environ.get("TEST_MAINTENANCE_PASSWORD", "dev_maintenance_pass_123")

    try:
        conn = await asyncpg.connect(connect_dsn)
    except Exception as e:
        # Redact connection details completely on error
        redacted_msg = sanitize_connection_error(str(e))
        print(f"ERROR: {redacted_msg}", file=sys.stderr)
        sys.exit(1)

    try:
        # 1. Idempotent Role Provisioning
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
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_bootstrap') THEN
                    CREATE ROLE db_bootstrap LOGIN PASSWORD '{bootstrap_pass}';
                END IF;
            END
            $$;
            """,
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                    CREATE ROLE db_api_user LOGIN PASSWORD '{api_pass}';
                END IF;
            END
            $$;
            """,
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                    CREATE ROLE db_ingestion_worker LOGIN PASSWORD '{worker_pass}';
                END IF;
            END
            $$;
            """,
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_maintenance_worker') THEN
                    CREATE ROLE db_maintenance_worker LOGIN PASSWORD '{maint_pass}';
                END IF;
            END
            $$;
            """,
        ]

        for stmt in role_statements:
            await conn.execute(stmt)

        # 2. Database Catalog Verification & Assertions
        app_user_info = await conn.fetchrow("SELECT rolname, rolcanlogin, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'db_app_user'")
        if not app_user_info:
            print("ERROR: CI_ROLE_PROVISIONING_CATALOG_FAILED: Role db_app_user missing.", file=sys.stderr)
            sys.exit(1)

        if app_user_info["rolcanlogin"]:
            print("ERROR: CI_ROLE_PROVISIONING_SECURITY_VIOLATION: db_app_user has LOGIN capability.", file=sys.stderr)
            sys.exit(1)

        if app_user_info["rolsuper"] or app_user_info["rolbypassrls"]:
            print("ERROR: CI_ROLE_PROVISIONING_SECURITY_VIOLATION: db_app_user has SUPERUSER or BYPASSRLS capability.", file=sys.stderr)
            sys.exit(1)

        member_count = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_auth_members WHERE roleid = (SELECT oid FROM pg_roles WHERE rolname = 'db_app_user')"
        )
        if member_count > 0:
            print("ERROR: CI_ROLE_PROVISIONING_SECURITY_VIOLATION: db_app_user has active members.", file=sys.stderr)
            sys.exit(1)

        print("SINGLE SOURCE CI ROLE PROVISIONING SUCCESSFUL!")
        print("STATIC_EVENT_CODE: CI_ROLE_PROVISIONING_SUCCESS")
        print("Verified Catalog: db_app_user is NOLOGIN, NOBYPASSRLS, NOSUPERUSER with 0 members.")

    except Exception as e:
        redacted_msg = sanitize_connection_error(str(e))
        print(f"ERROR: {redacted_msg}", file=sys.stderr)
        sys.exit(1)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Canonical Single-Source CI Role Provisioning Tool with Credential Redaction")
    parser.add_argument(
        "--target-url",
        default=os.environ.get("DATABASE_URL"),
        help="Target PostgreSQL DSN URL (must be provided via argument or DATABASE_URL env var)",
    )
    parser.add_argument(
        "--allow-local-test",
        action="store_true",
        help="Explicit flag for local development testing without CI=true marker",
    )
    args = parser.parse_args()

    if not args.target_url:
        print("ERROR: CI_ROLE_PROVISIONING_TARGET_REQUIRED: Target URL must be specified.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(provision_ci_roles(args.target_url, allow_local=args.allow_local_test))


if __name__ == "__main__":
    main()
