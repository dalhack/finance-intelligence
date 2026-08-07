import argparse
import asyncio
import os
import sys
from urllib.parse import urlparse

import asyncpg

ALLOWED_LOGIN_ROLES = {
    "db_bootstrap",
    "db_api_user",
    "db_ingestion_worker",
    "db_maintenance_worker",
}


def sanitize_connection_error(error_msg: str) -> str:
    """Strip sensitive information like passwords, usernames, and DSNs from error messages."""
    return "CI_ROLE_PROVISIONING_CONNECTION_FAILED: Connection to target database failed."


def validate_credential_contract() -> dict[str, str]:
    """Strict validation of CI test role password environment contract.

    Fails closed BEFORE opening database connection if any variable is missing or empty.
    Zero string fallback constants permitted.
    """
    required_envs = {
        "db_bootstrap": "TEST_BOOTSTRAP_PASSWORD",
        "db_api_user": "TEST_API_PASSWORD",
        "db_ingestion_worker": "TEST_WORKER_PASSWORD",
        "db_maintenance_worker": "TEST_MAINTENANCE_PASSWORD",
    }

    credentials = {}
    missing_vars = []

    for role_name, env_var in required_envs.items():
        val = os.environ.get(env_var)
        if not val or not val.strip():
            missing_vars.append(env_var)
        else:
            credentials[role_name] = val.strip()

    if missing_vars:
        print(
            f"ERROR: CI_ROLE_PROVISIONING_CREDENTIAL_CONTRACT_INCOMPLETE: Required env vars missing or empty: {', '.join(missing_vars)}",
            file=sys.stderr,
        )
        sys.exit(1)

    return credentials


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
    except Exception:  # noqa: BLE001
        print("ERROR: CI_ROLE_PROVISIONING_INVALID_DSN: Could not parse target DSN.", file=sys.stderr)
        sys.exit(1)

    hostname = (parsed.hostname or "").lower()
    dbname = (parsed.path.lstrip("/") or "").lower()

    # 3. Production Target Ban
    if "prod" in hostname or "production" in hostname or "prod" in dbname or "production" in dbname:
        print(
            "ERROR: CI_ROLE_PROVISIONING_PRODUCTION_TARGET_FORBIDDEN: Target is marked as production.", file=sys.stderr
        )
        sys.exit(1)

    # 4. Strict Loopback / Service-Container Allowlist
    safe_hosts = {"localhost", "127.0.0.1", "postgres", "0.0.0.0"}
    is_safe_host = hostname in safe_hosts
    is_safe_db = "test" in dbname or "roundtrip" in dbname or "ci" in dbname

    if not (is_safe_host and is_safe_db):
        print(
            f"ERROR: CI_ROLE_PROVISIONING_TARGET_NOT_ALLOWED: Target DB ({hostname}/{dbname}) not in CI allowlist.",
            file=sys.stderr,
        )
        sys.exit(1)


async def provision_ci_roles(dsn: str, allow_local: bool = False) -> None:
    # 1. Validate Credential Contract FIRST (Fail-Closed before connection)
    role_passwords = validate_credential_contract()

    # 2. Verify Target Allowlist & CI Marker
    verify_ci_target_allowlist(dsn, allow_local)

    connect_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = await asyncpg.connect(connect_dsn)
    except Exception as e:  # noqa: BLE001
        redacted_msg = sanitize_connection_error(str(e))
        print(f"ERROR: {redacted_msg}", file=sys.stderr)
        sys.exit(1)

    try:
        # 3. Provision db_app_user (Strict NOLOGIN compatibility role - no password parameter)
        app_user_sql = """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_app_user') THEN
                CREATE ROLE db_app_user NOLOGIN NOINHERIT;
            END IF;
        END
        $$;
        """
        await conn.execute(app_user_sql)

        # 4. Server-Side Escaped Role Provisioning using PostgreSQL quote_literal
        for role_name, password in role_passwords.items():
            if role_name not in ALLOWED_LOGIN_ROLES:
                print(
                    f"ERROR: CI_ROLE_PROVISIONING_UNAUTHORIZED_ROLE: Role {role_name} not in allowlist.",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Use PostgreSQL engine to safely escape password into a 100% injection-proof literal
            quoted_pass = await conn.fetchval("SELECT quote_literal(CAST($1 AS text))", password)
            role_exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = $1)", role_name)

            if not role_exists:
                await conn.execute(f"CREATE ROLE {role_name} WITH LOGIN PASSWORD {quoted_pass};")
            else:
                await conn.execute(f"ALTER ROLE {role_name} WITH LOGIN PASSWORD {quoted_pass};")

        # 5. Schema ACL Hardening: Revoke PUBLIC access and grant explicit USAGE/DML to canonical runtime roles
        schema_acl_sql = """
        DO $$
        BEGIN
            REVOKE ALL ON SCHEMA public FROM PUBLIC;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_app_user') THEN
                REVOKE ALL ON SCHEMA public FROM db_app_user;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_owner') THEN
                GRANT USAGE ON SCHEMA public TO db_owner;
                GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO db_owner;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO db_owner;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_bootstrap') THEN
                GRANT USAGE ON SCHEMA public TO db_bootstrap;
                GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO db_bootstrap;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO db_bootstrap;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN
                GRANT USAGE ON SCHEMA public TO db_api_user;
                GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO db_api_user;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO db_api_user;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN
                GRANT USAGE ON SCHEMA public TO db_ingestion_worker;
                GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO db_ingestion_worker;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO db_ingestion_worker;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_maintenance_worker') THEN
                GRANT USAGE ON SCHEMA public TO db_maintenance_worker;
                GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO db_maintenance_worker;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO db_maintenance_worker;
            END IF;
        END
        $$;
        """
        await conn.execute(schema_acl_sql)


        # 6. Database Catalog Verification & Security Assertions
        app_user_info = await conn.fetchrow(
            "SELECT rolname, rolcanlogin, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'db_app_user'"
        )
        if not app_user_info:
            print("ERROR: CI_ROLE_PROVISIONING_CATALOG_FAILED: Role db_app_user missing.", file=sys.stderr)
            sys.exit(1)

        if app_user_info["rolcanlogin"]:
            print("ERROR: CI_ROLE_PROVISIONING_SECURITY_VIOLATION: db_app_user has LOGIN capability.", file=sys.stderr)
            sys.exit(1)

        if app_user_info["rolsuper"] or app_user_info["rolbypassrls"]:
            print(
                "ERROR: CI_ROLE_PROVISIONING_SECURITY_VIOLATION: db_app_user has SUPERUSER or BYPASSRLS capability.",
                file=sys.stderr,
            )
            sys.exit(1)

        member_count = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_auth_members WHERE roleid = (SELECT oid FROM pg_roles WHERE rolname = 'db_app_user')"
        )
        if int(member_count or 0) > 0:
            print("ERROR: CI_ROLE_PROVISIONING_SECURITY_VIOLATION: db_app_user has active members.", file=sys.stderr)
            sys.exit(1)

        has_schema_usage = await conn.fetchval("SELECT has_schema_privilege('db_app_user', 'public', 'USAGE');")
        if has_schema_usage:
            print(
                "ERROR: CI_ROLE_PROVISIONING_SECURITY_VIOLATION: db_app_user retains effective public schema USAGE.",
                file=sys.stderr,
            )
            sys.exit(1)

        print("SINGLE SOURCE CI ROLE PROVISIONING SUCCESSFUL!")
        print("STATIC_EVENT_CODE: CI_ROLE_PROVISIONING_SUCCESS")
        print("Verified Catalog: db_app_user is NOLOGIN, NOBYPASSRLS, NOSUPERUSER with 0 members and 0 schema usage.")

    except Exception as e:  # noqa: BLE001
        redacted_msg = sanitize_connection_error(str(e))
        print(f"ERROR: {redacted_msg}", file=sys.stderr)
        sys.exit(1)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Canonical Single-Source CI Role Provisioning Tool with Parameterized SQL and Zero Fallbacks"
    )
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
