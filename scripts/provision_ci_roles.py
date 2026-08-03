import os
import sys
import asyncpg
import asyncio

async def provision_roles(dsn: str):
    conn = await asyncpg.connect(dsn)
    try:
        roles_sql = [
            "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_app_user') THEN CREATE ROLE db_app_user NOLOGIN NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT; END IF; END $$;",
            "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_bootstrap') THEN CREATE ROLE db_bootstrap LOGIN PASSWORD 'bootstrap_pass'; END IF; END $$;",
            "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_api_user') THEN CREATE ROLE db_api_user LOGIN PASSWORD 'api_pass'; END IF; END $$;",
            "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_ingestion_worker') THEN CREATE ROLE db_ingestion_worker LOGIN PASSWORD 'worker_pass'; END IF; END $$;",
            "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'db_maintenance_worker') THEN CREATE ROLE db_maintenance_worker LOGIN PASSWORD 'dev_maintenance_pass_123'; END IF; END $$;",
        ]
        for sql in roles_sql:
            await conn.execute(sql)
        print("CI PostgreSQL roles provisioned successfully (including db_app_user NOLOGIN compatibility role).")
    finally:
        await conn.close()

if __name__ == "__main__":
    db_url = os.environ.get("DATABASE_URL", "postgresql://db_owner:owner_pass@localhost:5432/finance_intelligence_test")
    # Convert asyncpg driver prefix if needed
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    asyncio.run(provision_roles(db_url))
