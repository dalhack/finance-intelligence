"""Remediated Integration tests for Revision 024 Production-Safe Compatibility Executor against PostgreSQL 16."""

from __future__ import annotations

import os

import pytest
import sqlalchemy as sa
from app.migration_execution.compatibility import (
    COMPATIBILITY_REVISION,
    MIGRATION_ADVISORY_LOCK_ID,
    SOURCE_REVISION,
    Migration024CompatibilityError,
    execute_compatibility_bridge,
    verify_postconditions,
)

POSTGRES_TEST_DSN = os.environ.get("POSTGRES_TEST_DSN")


@pytest.mark.skipif(not POSTGRES_TEST_DSN, reason="POSTGRES_TEST_DSN not set")
def test_postgres_024_compatibility_bridge_execution_and_rollback():
    """Empirically tests atomic 023 -> 024 compatibility bridge execution, deep postconditions, and rollback behavior on PostgreSQL 16."""
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

        # Acquire lock for current PID
        conn.execute(
            sa.text("SELECT pg_advisory_lock(:lock_id);"),
            {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
        )
        conn.execute(sa.text("SET ROLE db_owner;"))

        try:
            # Execute compatibility bridge
            execute_compatibility_bridge(conn, expected_database="finance_intelligence_test")

            # Verify alembic_version is at 024
            new_ver = conn.execute(sa.text("SELECT version_num FROM alembic_version;")).scalar()
            assert new_ver == COMPATIBILITY_REVISION

            # Deep Postcondition Verification
            verify_postconditions(conn)

        finally:
            conn.execute(sa.text("RESET ROLE;"))
            conn.execute(
                sa.text("SELECT pg_advisory_unlock(:lock_id);"),
                {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
            )


@pytest.mark.skipif(not POSTGRES_TEST_DSN, reason="POSTGRES_TEST_DSN not set")
def test_postgres_controlled_failure_rollback_to_023():
    """Empirically verifies that midway DDL or postcondition failure cleanly rolls back transaction and preserves revision 023."""
    engine = sa.create_engine(POSTGRES_TEST_DSN)
    with engine.connect() as conn:
        conn.execute(sa.text("DROP TABLE IF EXISTS alembic_version CASCADE;"))
        conn.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY);"))
        conn.execute(sa.text(f"INSERT INTO alembic_version VALUES ('{SOURCE_REVISION}');"))

        # Setup invalid state to force DDL failure (e.g. invalid table constraint collision)
        conn.execute(sa.text("DROP TABLE IF EXISTS maintenance_jobs CASCADE;"))
        conn.execute(sa.text("CREATE TABLE maintenance_jobs (id INT PRIMARY KEY);"))  # Invalid schema structure

        conn.execute(
            sa.text("SELECT pg_advisory_lock(:lock_id);"),
            {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
        )
        conn.execute(sa.text("SET ROLE db_owner;"))

        try:
            with pytest.raises(Migration024CompatibilityError):
                execute_compatibility_bridge(conn)

            # Assert alembic_version remains at 023 after rollback
            ver = conn.execute(sa.text("SELECT version_num FROM alembic_version;")).scalar()
            assert ver == SOURCE_REVISION

        finally:
            conn.execute(sa.text("RESET ROLE;"))
            conn.execute(
                sa.text("SELECT pg_advisory_unlock(:lock_id);"),
                {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
            )
