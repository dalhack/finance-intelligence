"""Unit tests for single-run local iOS application E2E harness (scripts/run_local_ios_e2e.py)."""

import json
import os
import stat
import tempfile
import uuid
import pytest

from scripts.run_local_ios_e2e import (
    AtomicExecutionLedger,
    FixtureManifest,
    LedgerError,
    LocalTargetSafetyError,
    build_flutter_argv,
    check_credential_presence,
    compute_command_hash,
    generate_fixture_manifest,
    redact_sensitive_text,
    run_harness_dry_run,
    validate_local_loopback_url,
)


def test_ledger_atomic_exclusive_create():
    """Verify AtomicExecutionLedger creates ledger file exclusively with 0600 mode and blocks second run."""
    auth_id = f"test-auth-{uuid.uuid4().hex[:8]}"
    ledger = AtomicExecutionLedger(auth_id)

    try:
        data = ledger.create_exclusive(
            command_hash="a" * 64,
            target_head="596d85055cff352e70085d7490427be7d2f08a69",
            device_id="0C58FDA6-FED4-449E-A3C9-40ACE41F9612",
        )
        assert data["authorization_id"] == auth_id
        assert data["state"] == "RESERVED"
        assert data["execution_count"] == 0

        # Verify mode is 0600 (read/write by owner only)
        st = os.stat(ledger.ledger_path)
        mode = stat.S_IMODE(st.st_mode)
        assert mode == 0o600

        # Attempting second create_exclusive with same auth_id fails
        with pytest.raises(LedgerError) as exc_info:
            ledger.create_exclusive("b" * 64, "596d85055cff352e70085d7490427be7d2f08a69", "device-2")
        assert "LEDGER_ALREADY_EXISTS" in str(exc_info.value)
    finally:
        if os.path.exists(ledger.ledger_path):
            os.remove(ledger.ledger_path)


def test_ledger_state_transition_and_execution_limit():
    """Verify ledger state transition updates state atomically and enforces execution_count <= 1."""
    auth_id = f"test-limit-{uuid.uuid4().hex[:8]}"
    ledger = AtomicExecutionLedger(auth_id)

    try:
        ledger.create_exclusive("a" * 64, "596d85055cff352e70085d7490427be7d2f08a69", "dev-1")
        updated = ledger.atomic_update_state("STARTED", execution_count=1)
        assert updated["state"] == "STARTED"
        assert updated["execution_count"] == 1

        # Attempting execution_count > 1 raises LedgerError
        with pytest.raises(LedgerError) as exc_info:
            ledger.atomic_update_state("STARTED", execution_count=2)
        assert "EXECUTION_COUNT_EXCEEDED" in str(exc_info.value)
    finally:
        if os.path.exists(ledger.ledger_path):
            os.remove(ledger.ledger_path)


def test_local_target_safety_guard():
    """Verify local target safety guard approves loopback URLs and rejects remote/staging targets."""
    # Loopback targets -> Pass
    validate_local_loopback_url("postgresql+asyncpg://user:pass@127.0.0.1:5433/finance_intelligence_test", "DB_URL")
    validate_local_loopback_url("postgresql+asyncpg://user:pass@localhost:5433/finance_intelligence_test", "DB_URL")
    validate_local_loopback_url("http://127.0.0.1:8000", "API_URL")

    # Staging/remote targets -> Reject
    with pytest.raises(LocalTargetSafetyError):
        validate_local_loopback_url("postgresql+asyncpg://user:pass@staging-db.example.com:5432/finance_intelligence_prod", "DB_URL")

    with pytest.raises(LocalTargetSafetyError):
        validate_local_loopback_url("postgresql+asyncpg://user:pass@10.0.0.5:5432/finance_intelligence_test", "DB_URL")

    with pytest.raises(LocalTargetSafetyError):
        validate_local_loopback_url("https://cloudsql.googleapis.com/sql/v1/projects/my-proj", "DB_URL")


def test_fixture_manifest_uuidv5_derivation():
    """Verify fixture manifest derives deterministic entity UUIDs from run_namespace."""
    auth_id = f"test-manifest-{uuid.uuid4().hex[:8]}"
    m1 = generate_fixture_manifest(auth_id)
    m2 = generate_fixture_manifest(auth_id)

    # Each call produces a fresh run_namespace
    assert m1.run_namespace != m2.run_namespace

    # Within a single manifest, entity IDs are distinct
    ids = {m1.organization_id, m1.actor_id, m1.institution_id, m1.reporting_period_id}
    assert len(ids) == 4

    # Each ID is a valid UUID
    for id_str in ids:
        val = uuid.UUID(id_str)
        assert val.version == 5


def test_command_hash_and_define_parity():
    """Verify build_flutter_argv produces exactly 7 unique --dart-define parameters with CLI authorization_id provenance."""
    auth_id = "auth-slice4-r5-78f6f9d-01"
    manifest = generate_fixture_manifest(auth_id)
    argv = build_flutter_argv("device-sim-123", manifest, authorization_id=auth_id, api_base_url="http://127.0.0.1:8000")

    defines = [arg for arg in argv if arg.startswith("--dart-define=")]
    assert len(defines) == 7
    assert len(set(defines)) == 7  # 7 unique defines, zero duplicates

    define_map = dict(d.replace("--dart-define=", "").split("=", 1) for d in defines)
    assert define_map["FI_E2E_API_BASE_URL"] == "http://127.0.0.1:8000"
    assert define_map["FI_E2E_AUTHORIZATION_ID"] == auth_id
    assert define_map["FI_E2E_AUTHORIZATION_ID"] != manifest.run_namespace
    assert define_map["FI_E2E_ORGANIZATION_ID"] == manifest.organization_id
    assert define_map["FI_E2E_ACTOR_ID"] == manifest.actor_id
    assert define_map["FI_E2E_INSTITUTION_ID"] == manifest.institution_id
    assert define_map["FI_E2E_REPORTING_PERIOD_ID"] == manifest.reporting_period_id
    assert define_map["FI_E2E_FIXTURE_FILE_PATH"].startswith(f"/private/tmp/fi-fixture-{manifest.run_namespace}")

    h1 = compute_command_hash(argv)
    assert len(h1) == 64



def test_harness_fixture_file_creation_and_cleanup():
    """Verify run_harness_execute creates ephemeral 0600 fixture file if missing and cleans it up on both pass and fail paths."""
    from scripts.run_local_ios_e2e import run_harness_execute

    auth_id = f"test-fix-clean-{uuid.uuid4().hex[:8]}"
    created_fixture_path = None

    def mock_runner(argv):
        nonlocal created_fixture_path
        define_map = dict(d.replace("--dart-define=", "").split("=", 1) for d in argv if d.startswith("--dart-define="))
        created_fixture_path = define_map["FI_E2E_FIXTURE_FILE_PATH"]
        assert os.path.exists(created_fixture_path)
        # Verify 0600 mode
        st = os.stat(created_fixture_path)
        assert stat.S_IMODE(st.st_mode) == 0o600
        return 0

    res = run_harness_execute(
        authorization_id=auth_id,
        device_id="device-sim-999",
        runner_fn=mock_runner,
    )

    assert res["status"] == "EXECUTION_SUCCESS"
    assert res["emitted_define_count"] == 7
    assert res["unique_define_count"] == 7
    assert created_fixture_path is not None
    # Verify cleanup deleted the harness-created fixture file
    assert not os.path.exists(created_fixture_path)

    # Clean up ledger
    if os.path.exists(res["ledger_path"]):
        os.remove(res["ledger_path"])



def test_evidence_redaction():
    """Verify redact_sensitive_text redacts Anthropic API keys, Bearer tokens, and database passwords."""
    raw = "Header: Bearer eyJhbGciOi... Key: sk-ant-api03-abcdef1234567890 password=secret_pass_123"
    redacted = redact_sensitive_text(raw)

    assert "sk-ant-api03" not in redacted
    assert "[REDACTED_API_KEY]" in redacted
    assert "eyJhbGciOi" not in redacted
    assert "[REDACTED_TOKEN]" in redacted
    assert "secret_pass_123" not in redacted
    assert "[REDACTED_PASSWORD]" in redacted


def test_harness_dry_run_mode():
    """Verify dry-run mode returns structured plan without DB writes, process starts, or test executions."""
    auth_id = f"test-dry-{uuid.uuid4().hex[:8]}"
    plan = run_harness_dry_run(auth_id, "device-sim-123")

    assert plan["status"] == "DRY_RUN_SUCCESS"
    assert plan["mode"] == "dry-run"
    assert plan["authorization_id"] == auth_id
    assert plan["device_id"] == "device-sim-123"
    assert plan["db_writes_count"] == 0
    assert plan["processes_started_count"] == 0
    assert plan["flutter_tests_executed_count"] == 0
    assert "command_argv" in plan
    assert "command_sha256" in plan


def test_harness_execute_pipeline_success():
    """Verify run_harness_execute runs full lifecycle: ledger reserve -> seed -> runner -> cleanup -> ledger finalize."""
    from scripts.run_local_ios_e2e import run_harness_execute

    auth_id = f"test-exec-{uuid.uuid4().hex[:8]}"
    events = []

    def mock_seed(manifest):
        events.append("SEED")

    def mock_service_launcher():
        events.append("SERVICES_STARTED")

    def mock_runner(argv):
        events.append("RUNNER_EXECUTED")
        return 0

    def mock_cleanup(manifest):
        events.append("CLEANUP")

    res = run_harness_execute(
        authorization_id=auth_id,
        device_id="device-sim-999",
        runner_fn=mock_runner,
        seed_fn=mock_seed,
        cleanup_fn=mock_cleanup,
        service_launcher_fn=mock_service_launcher,
    )

    assert res["status"] == "EXECUTION_SUCCESS"
    assert res["execution_result"] == "PASSED"
    assert res["cleanup_status"] == "COMPLETE"
    assert events == ["SEED", "SERVICES_STARTED", "RUNNER_EXECUTED", "CLEANUP"]

    # Verify ledger file is in CLEANUP_COMPLETE state
    ledger_path = res["ledger_path"]
    assert os.path.exists(ledger_path)
    with open(ledger_path) as f:
        data = json.load(f)
    assert data["state"] == "CLEANUP_COMPLETE"
    assert data["execution_count"] == 1
    os.remove(ledger_path)


def test_harness_execute_pipeline_failure_runs_cleanup():
    """Verify run_harness_execute runs cleanup in finally block even when runner fails."""
    from scripts.run_local_ios_e2e import run_harness_execute

    auth_id = f"test-fail-{uuid.uuid4().hex[:8]}"
    events = []

    def mock_runner(argv):
        events.append("RUNNER_FAILED")
        return 1

    def mock_cleanup(manifest):
        events.append("CLEANUP")

    res = run_harness_execute(
        authorization_id=auth_id,
        device_id="device-sim-999",
        runner_fn=mock_runner,
        cleanup_fn=mock_cleanup,
    )

    assert res["status"] == "EXECUTION_FAILED"
    assert res["execution_result"] == "FAILED"
    assert res["cleanup_status"] == "COMPLETE"
    assert events == ["RUNNER_FAILED", "CLEANUP"]

    ledger_path = res["ledger_path"]
    if os.path.exists(ledger_path):
        os.remove(ledger_path)

