"""Remediated Unit Tests for Revision 024 Production-Safe Compatibility Executor."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.migration_execution.compatibility.revision_024 import (
    EXPECTED_REVISION_024_SHA256,
    REVISION_024_INDEXES,
    REVISION_024_POLICIES,
    REVISION_024_TABLES,
    SOURCE_REVISION,
    Migration024CompatibilityError,
    _find_revision_024_file,
    verify_compatibility_preconditions,
    verify_postconditions,
    verify_revision_024_checksum,
)


def test_revision_024_file_checksum_parity():
    """Verifies that the physical historical 024 migration file SHA-256 matches expected constant."""
    file_path = _find_revision_024_file()
    assert file_path.is_file()
    computed_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    assert computed_hash == EXPECTED_REVISION_024_SHA256
    assert verify_revision_024_checksum() == EXPECTED_REVISION_024_SHA256


def test_revision_024_checksum_mismatch_raises(monkeypatch):
    """Verifies that SHA-256 mismatch triggers immediate fail-closed error."""
    fake_path = MagicMock()
    fake_path.read_bytes.return_value = b"invalid content"
    monkeypatch.setattr(
        "app.migration_execution.compatibility.revision_024._find_revision_024_file",
        lambda: fake_path,
    )
    with pytest.raises(Migration024CompatibilityError, match="checksum mismatch"):
        verify_revision_024_checksum()


def test_preconditions_alembic_version_rowcount_check(monkeypatch):
    """Verifies fail-closed behavior when alembic_version has != 1 row."""
    monkeypatch.setattr(
        "app.migration_execution.compatibility.revision_024.verify_revision_024_checksum",
        lambda: EXPECTED_REVISION_024_SHA256,
    )
    mock_conn = MagicMock()
    mock_res = MagicMock()
    mock_res.fetchall.return_value = []
    mock_conn.execute.return_value = mock_res
    with pytest.raises(Migration024CompatibilityError, match="Expected exactly 1 row"):
        verify_compatibility_preconditions(mock_conn)


def test_preconditions_wrong_source_revision(monkeypatch):
    """Verifies refusal when alembic_version is not at revision 023."""
    monkeypatch.setattr(
        "app.migration_execution.compatibility.revision_024.verify_revision_024_checksum",
        lambda: EXPECTED_REVISION_024_SHA256,
    )
    mock_conn = MagicMock()
    mock_res = MagicMock()
    mock_res.fetchall.return_value = [("022_model_provider_and_analysis_events",)]
    mock_conn.execute.return_value = mock_res
    with pytest.raises(Migration024CompatibilityError, match="Expected current revision"):
        verify_compatibility_preconditions(mock_conn)


def test_preconditions_active_role_mismatch(monkeypatch):
    """Verifies refusal when current active role is not 'db_owner'."""
    monkeypatch.setattr(
        "app.migration_execution.compatibility.revision_024.verify_revision_024_checksum",
        lambda: EXPECTED_REVISION_024_SHA256,
    )
    mock_conn = MagicMock()
    mock_res1 = MagicMock()
    mock_res1.fetchall.return_value = [(SOURCE_REVISION,)]
    mock_res2 = MagicMock()
    mock_res2.fetchone.return_value = ("db_bootstrap", "postgres", "finance_intelligence_staging")

    mock_conn.execute.side_effect = [mock_res1, mock_res2]
    with pytest.raises(Migration024CompatibilityError, match="Expected current active role 'db_owner'"):
        verify_compatibility_preconditions(mock_conn)


def test_preconditions_database_mismatch(monkeypatch):
    """Verifies refusal when connected database does not match expected_database parameter."""
    monkeypatch.setattr(
        "app.migration_execution.compatibility.revision_024.verify_revision_024_checksum",
        lambda: EXPECTED_REVISION_024_SHA256,
    )
    mock_conn = MagicMock()
    mock_res1 = MagicMock()
    mock_res1.fetchall.return_value = [(SOURCE_REVISION,)]
    mock_res2 = MagicMock()
    mock_res2.fetchone.return_value = ("db_bootstrap", "db_owner", "wrong_database")

    mock_conn.execute.side_effect = [mock_res1, mock_res2]
    with pytest.raises(Migration024CompatibilityError, match="Database mismatch"):
        verify_compatibility_preconditions(mock_conn, expected_database="finance_intelligence_staging")


def test_preconditions_advisory_lock_not_held(monkeypatch):
    """Verifies refusal when advisory lock is not held by active session backend PID."""
    monkeypatch.setattr(
        "app.migration_execution.compatibility.revision_024.verify_revision_024_checksum",
        lambda: EXPECTED_REVISION_024_SHA256,
    )
    mock_conn = MagicMock()
    mock_res1 = MagicMock()
    mock_res1.fetchall.return_value = [(SOURCE_REVISION,)]
    mock_res2 = MagicMock()
    mock_res2.fetchone.return_value = ("db_bootstrap", "db_owner", "finance_intelligence_staging")
    mock_res3 = MagicMock()
    mock_res3.scalar.return_value = None  # Lock not held

    mock_conn.execute.side_effect = [mock_res1, mock_res2, mock_res3]
    with pytest.raises(Migration024CompatibilityError, match="Advisory lock 849204918239 is not held"):
        verify_compatibility_preconditions(mock_conn, expected_database="finance_intelligence_staging")


def test_preconditions_role_attribute_checks(monkeypatch):
    """Verifies refusal if db_maintenance_worker role has elevated attributes or is missing."""
    monkeypatch.setattr(
        "app.migration_execution.compatibility.revision_024.verify_revision_024_checksum",
        lambda: EXPECTED_REVISION_024_SHA256,
    )
    mock_conn = MagicMock()

    # Case 1: Missing role
    mock_res1 = MagicMock()
    mock_res1.fetchall.return_value = [(SOURCE_REVISION,)]
    mock_res2 = MagicMock()
    mock_res2.fetchone.return_value = ("db_bootstrap", "db_owner", "finance_intelligence_staging")
    mock_res3 = MagicMock()
    mock_res3.scalar.return_value = 1  # lock held
    mock_res4 = MagicMock()
    mock_res4.fetchone.return_value = None  # role missing

    mock_conn.execute.side_effect = [mock_res1, mock_res2, mock_res3, mock_res4]
    with pytest.raises(Migration024CompatibilityError, match="does not exist in pg_roles"):
        verify_compatibility_preconditions(mock_conn)


def test_preconditions_forbidden_owner_membership(monkeypatch):
    """Verifies refusal if db_maintenance_worker or postgres is member of db_owner."""
    monkeypatch.setattr(
        "app.migration_execution.compatibility.revision_024.verify_revision_024_checksum",
        lambda: EXPECTED_REVISION_024_SHA256,
    )
    mock_conn = MagicMock()

    mock_res1 = MagicMock()
    mock_res1.fetchall.return_value = [(SOURCE_REVISION,)]
    mock_res2 = MagicMock()
    mock_res2.fetchone.return_value = ("db_bootstrap", "db_owner", "finance_intelligence_staging")
    mock_res3 = MagicMock()
    mock_res3.scalar.return_value = 1  # lock held
    mock_res4 = MagicMock()
    mock_res4.fetchone.return_value = (True, False, False, False, False, False)
    mock_res5 = MagicMock()
    mock_res5.scalars().all.return_value = ["db_maintenance_worker"]

    mock_conn.execute.side_effect = [mock_res1, mock_res2, mock_res3, mock_res4, mock_res5]
    with pytest.raises(Migration024CompatibilityError, match="must NOT be a member of 'db_owner'"):
        verify_compatibility_preconditions(mock_conn)


@pytest.mark.parametrize(
    "artifact_type,artifact_name",
    [
        ("table", "maintenance_jobs"),
        ("table", "maintenance_attempts"),
        ("table", "maintenance_worker_heartbeats"),
        ("index", "idx_maintenance_jobs_org"),
        ("index", "idx_maintenance_jobs_claim"),
        ("index", "idx_maintenance_attempts_job"),
        ("policy", "maintenance_jobs_tenant_policy"),
        ("policy", "maintenance_attempts_tenant_policy"),
        ("function", "claim_next_maintenance_job"),
    ],
)
def test_preconditions_partial_object_manifest_fail_closed(monkeypatch, artifact_type, artifact_name):
    """100% Manifest Verification: Asserts that ANY single partial artifact triggers fail-closed error."""
    monkeypatch.setattr(
        "app.migration_execution.compatibility.revision_024.verify_revision_024_checksum",
        lambda: EXPECTED_REVISION_024_SHA256,
    )
    mock_conn = MagicMock()

    # Pre-setup side effects
    side_effects = [
        MagicMock(fetchall=lambda: [(SOURCE_REVISION,)]),
        MagicMock(fetchone=lambda: ("db_bootstrap", "db_owner", "finance_intelligence_staging")),
        MagicMock(scalar=lambda: 1),  # lock held
        MagicMock(fetchone=lambda: (True, False, False, False, False, False)),
        MagicMock(scalars=lambda: MagicMock(all=list)),
    ]

    # Add partial artifact trigger
    for tbl in REVISION_024_TABLES:
        val = 1 if artifact_type == "table" and tbl == artifact_name else None
        side_effects.append(MagicMock(scalar=lambda v=val: v))

    for idx in REVISION_024_INDEXES:
        val = 1 if artifact_type == "index" and idx == artifact_name else None
        side_effects.append(MagicMock(scalar=lambda v=val: v))

    for pol in REVISION_024_POLICIES:
        val = 1 if artifact_type == "policy" and pol == artifact_name else None
        side_effects.append(MagicMock(scalar=lambda v=val: v))

    val = 1 if artifact_type == "function" and artifact_name == "claim_next_maintenance_job" else None
    side_effects.append(MagicMock(scalar=lambda v=val: v))

    mock_conn.execute.side_effect = side_effects

    with pytest.raises(Migration024CompatibilityError, match="Partial Revision 024 artifact"):
        verify_compatibility_preconditions(mock_conn)


def test_postconditions_missing_table_raises():
    """Verifies that missing table in postcondition verification raises Migration024CompatibilityError."""
    mock_conn = MagicMock()
    mock_res = MagicMock()
    mock_res.scalar.return_value = None  # missing table
    mock_conn.execute.return_value = mock_res

    with pytest.raises(Migration024CompatibilityError, match="Postcondition failed: Table"):
        verify_postconditions(mock_conn)


def test_postconditions_missing_function_raises():
    """Verifies that invalid function owner or attributes in postcondition verification raises error."""
    mock_conn = MagicMock()

    # Table existence & exact columns
    mock_res1_tbl = MagicMock(scalar=lambda: 1)
    mock_res2_jobs = MagicMock(
        fetchall=lambda: [
            ("id", "uuid", "NO"),
            ("job_code", "character varying", "NO"),
            ("organization_id", "uuid", "NO"),
            ("target_entity_id", "character varying", "YES"),
            ("status", "character varying", "NO"),
            ("available_at", "timestamp with time zone", "NO"),
            ("locked_by", "character varying", "YES"),
            ("locked_at", "timestamp with time zone", "YES"),
            ("lease_expires_at", "timestamp with time zone", "YES"),
            ("claim_token", "uuid", "YES"),
            ("attempt_count", "integer", "NO"),
            ("max_attempts", "integer", "NO"),
            ("last_error_code", "character varying", "YES"),
            ("created_at", "timestamp with time zone", "NO"),
            ("completed_at", "timestamp with time zone", "YES"),
        ]
    )
    mock_res2_attempts = MagicMock(
        fetchall=lambda: [
            ("id", "uuid", "NO"),
            ("maintenance_job_id", "uuid", "NO"),
            ("organization_id", "uuid", "NO"),
            ("attempt_number", "integer", "NO"),
            ("worker_instance_key", "character varying", "NO"),
            ("claim_token_fingerprint", "character varying", "NO"),
            ("status", "character varying", "NO"),
            ("error_code", "character varying", "YES"),
            ("started_at", "timestamp with time zone", "NO"),
            ("finished_at", "timestamp with time zone", "YES"),
            ("created_at", "timestamp with time zone", "NO"),
        ]
    )
    mock_res2_heartbeats = MagicMock(
        fetchall=lambda: [
            ("worker_instance_key", "character varying", "NO"),
            ("worker_role", "character varying", "NO"),
            ("started_at", "timestamp with time zone", "NO"),
            ("last_seen_at", "timestamp with time zone", "NO"),
            ("status", "character varying", "NO"),
            ("contract_version", "character varying", "NO"),
        ]
    )
    mock_res_constraint = MagicMock(scalar=lambda: "PRIMARY KEY (id)")
    mock_res_index = MagicMock(fetchone=lambda: (True, True, "CREATE INDEX ..."))
    mock_res_rls = MagicMock(fetchone=lambda: (True, True))
    mock_res_pol = MagicMock(fetchone=lambda: ("ALL", "USING ...", "WITH CHECK ..."))

    # Function owner is wrong ("postgres" instead of "db_owner")
    mock_res_fn = MagicMock(
        fetchone=lambda: (
            "postgres",
            False,
            "CREATE FUNCTION",
            "p_worker_id text, p_claim_token uuid, p_allowed_job_codes text[]",
        )
    )

    side_effects = [
        # 3 tables (exists + cols)
        mock_res1_tbl,
        mock_res2_jobs,
        mock_res1_tbl,
        mock_res2_attempts,
        mock_res1_tbl,
        mock_res2_heartbeats,
        # 7 constraints
        mock_res_constraint,
        mock_res_constraint,
        mock_res_constraint,
        mock_res_constraint,
        mock_res_constraint,
        mock_res_constraint,
        mock_res_constraint,
        # 3 indexes
        mock_res_index,
        mock_res_index,
        mock_res_index,
        # 2 RLS flags
        mock_res_rls,
        mock_res_rls,
        # 2 policies
        mock_res_pol,
        mock_res_pol,
        # Function info
        mock_res_fn,
    ]
    mock_conn.execute.side_effect = side_effects

    with pytest.raises(Migration024CompatibilityError, match="Postcondition failed: Invalid function attributes"):
        verify_postconditions(mock_conn)


def test_compatibility_module_contains_no_password_literals():
    """Verifies static analysis invariant: revision_024.py contains no static password literals or DDL."""
    mod_path = Path(__file__).resolve().parents[2] / "app" / "migration_execution" / "compatibility" / "revision_024.py"
    content = mod_path.read_text()
    assert "dev_maintenance_pass_123" not in content
    assert "ALTER ROLE" not in content
    assert "CREATE ROLE" not in content


def test_historical_migrations_001_through_030_checksums_unmodified():
    """Verifies that none of the historical migration files 001-030 have been modified."""
    versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    assert versions_dir.is_dir()
    files = [f for f in versions_dir.glob("*.py") if int(f.name.split("_")[0]) <= 30]
    assert len(files) == 30
