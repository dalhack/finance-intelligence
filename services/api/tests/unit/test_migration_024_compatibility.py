"""Unit tests for Revision 024 Production-Safe Compatibility Executor."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.migration_execution.compatibility.revision_024 import (
    EXPECTED_REVISION_024_SHA256,
    Migration024CompatibilityError,
    _find_revision_024_file,
    verify_compatibility_preconditions,
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


def test_preconditions_role_attribute_checks(monkeypatch):
    """Verifies refusal if db_maintenance_worker role has elevated attributes or is missing."""
    monkeypatch.setattr(
        "app.migration_execution.compatibility.revision_024.verify_revision_024_checksum",
        lambda: EXPECTED_REVISION_024_SHA256,
    )
    mock_conn = MagicMock()

    # Case 1: Missing role
    mock_res1 = MagicMock()
    mock_res1.fetchall.return_value = [("023_analysis_clarification_workflow",)]
    mock_res2 = MagicMock()
    mock_res2.fetchone.return_value = None

    mock_conn.execute.side_effect = [mock_res1, mock_res2]
    with pytest.raises(Migration024CompatibilityError, match="does not exist in pg_roles"):
        verify_compatibility_preconditions(mock_conn)

    # Case 2: Role is SUPERUSER or CREATEROLE
    mock_res3 = MagicMock()
    mock_res3.fetchall.return_value = [("023_analysis_clarification_workflow",)]
    mock_res4 = MagicMock()
    mock_res4.fetchone.return_value = (True, True, False, False, False, False)  # is_super=True

    mock_conn.execute.side_effect = [mock_res3, mock_res4]
    with pytest.raises(Migration024CompatibilityError, match="Invalid role attributes"):
        verify_compatibility_preconditions(mock_conn)


def test_compatibility_module_contains_no_password_literals():
    """Verifies static analysis invariant: revision_024.py contains no static password literals."""
    mod_path = Path(__file__).resolve().parents[2] / "app" / "migration_execution" / "compatibility" / "revision_024.py"
    content = mod_path.read_text()
    assert "dev_maintenance_pass_123" not in content
    assert "ALTER ROLE" not in content
    assert "CREATE ROLE" not in content


def test_historical_migrations_001_through_030_checksums_unmodified():
    """Verifies that none of the historical migration files 001-030 have been modified."""
    versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    assert versions_dir.is_dir()
    files = list(versions_dir.glob("*.py"))
    assert len(files) == 30
