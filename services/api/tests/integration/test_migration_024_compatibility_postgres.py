"""Integration tests for Revision 024 Production-Safe Compatibility Executor against PostgreSQL 16."""

from __future__ import annotations

import os

import pytest
import sqlalchemy as sa
from app.migration_execution.compatibility import (
    COMPATIBILITY_REVISION,
    SOURCE_REVISION,
    execute_compatibility_bridge,
)

# Skip integration tests if no local postgres test DSN is configured
POSTGRES_TEST_DSN = os.environ.get("POSTGRES_TEST_DSN")


@pytest.mark.skipif(not POSTGRES_TEST_DSN, reason="POSTGRES_TEST_DSN not set")
def test_postgres_024_compatibility_bridge_execution():
    """Tests atomic 023 -> 024 compatibility bridge execution on real PostgreSQL 16 instance."""
    engine = sa.create_engine(POSTGRES_TEST_DSN)
    with engine.connect() as conn:
        # Setup pre-state: alembic_version at 023, db_maintenance_worker role exists
        conn.execute(sa.text("DROP TABLE IF EXISTS alembic_version CASCADE;"))
        conn.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY);"))
        conn.execute(sa.text(f"INSERT INTO alembic_version VALUES ('{SOURCE_REVISION}');"))

        # Setup test role db_maintenance_worker if missing
        role_exists = conn.execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = 'db_maintenance_worker';")).scalar()
        if not role_exists:
            conn.execute(
                sa.text(
                    "CREATE ROLE db_maintenance_worker LOGIN PASSWORD 'test_secret_pass_123' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;"
                )
            )

        # Setup required prerequisite tables from migrations 001-023
        conn.execute(sa.text("CREATE TABLE IF NOT EXISTS organizations (id UUID PRIMARY KEY);"))
        conn.execute(sa.text("CREATE TABLE IF NOT EXISTS analysis_jobs (id UUID PRIMARY KEY);"))
        conn.execute(sa.text("CREATE TABLE IF NOT EXISTS analysis_clarifications (id UUID PRIMARY KEY);"))
        conn.execute(sa.text("CREATE TABLE IF NOT EXISTS analysis_events (id UUID PRIMARY KEY);"))
        conn.execute(sa.text("CREATE TABLE IF NOT EXISTS audit_events (id UUID PRIMARY KEY);"))

        # Execute compatibility bridge
        execute_compatibility_bridge(conn)

        # Verify alembic_version is at 024
        new_ver = conn.execute(sa.text("SELECT version_num FROM alembic_version;")).scalar()
        assert new_ver == COMPATIBILITY_REVISION

        # Verify tables created
        for tbl in ["maintenance_jobs", "maintenance_attempts", "maintenance_worker_heartbeats"]:
            tbl_exists = conn.execute(
                sa.text(
                    f"SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{tbl}';"
                )
            ).scalar()
            assert tbl_exists

        # Verify function claim_next_maintenance_job exists
        fn_exists = conn.execute(
            sa.text(
                "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid "
                "WHERE n.nspname = 'public' AND p.proname = 'claim_next_maintenance_job';"
            )
        ).scalar()
        assert fn_exists
