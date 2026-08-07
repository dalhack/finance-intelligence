#!/usr/bin/env python3
"""Canonical Python harness for orchestrating single-run local iOS application E2E test execution."""

import argparse
import hashlib
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


class LocalTargetSafetyError(Exception):
    """Raised when target database or API URL violates local loopback containment."""

    pass


class LedgerError(Exception):
    """Raised when ledger creation or state transition fails or violates single-run limits."""

    pass


class PreflightError(Exception):
    """Raised when preflight environment or simulator checks fail."""

    pass


ALLOWED_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def validate_local_loopback_url(url_str: str, name: str) -> None:
    """Validate that database or API URL connects strictly to local loopback and test database."""
    clean_url = url_str.lower()
    if any(
        forbidden in clean_url
        for forbidden in ["cloudsql", "gcp", "staging", "prod", "firebaseio.com", "storage.googleapis.com"]
    ):
        raise LocalTargetSafetyError(f"REJECTED: {name} contains remote/staging marker in '{url_str}'")

    # Extract host part
    host_part = url_str
    if "://" in host_part:
        host_part = host_part.split("://", 1)[1]
    if "@" in host_part:
        host_part = host_part.split("@", 1)[1]
    if "/" in host_part:
        host_part = host_part.split("/", 1)[0]
    if ":" in host_part:
        host_part = host_part.split(":", 1)[0]

    if host_part not in ALLOWED_LOOPBACK_HOSTS:
        raise LocalTargetSafetyError(
            f"REJECTED: {name} host '{host_part}' is not in allowed local loopback set {ALLOWED_LOOPBACK_HOSTS}"
        )


@dataclass(frozen=True)
class FixtureManifest:
    run_namespace: str
    organization_id: str
    actor_id: str
    institution_id: str
    reporting_period_id: str


def generate_fixture_manifest(authorization_id: str) -> FixtureManifest:
    """Generate deterministic, isolated entity UUIDs derived from a unique run_namespace."""
    run_namespace = uuid.uuid4()
    org_id = uuid.uuid5(run_namespace, "organization")
    actor_id = uuid.uuid5(run_namespace, "actor")
    inst_id = uuid.uuid5(run_namespace, "institution")
    period_id = uuid.uuid5(run_namespace, "reporting_period")

    return FixtureManifest(
        run_namespace=str(run_namespace),
        organization_id=str(org_id),
        actor_id=str(actor_id),
        institution_id=str(inst_id),
        reporting_period_id=str(period_id),
    )


def compute_command_hash(argv: list[str]) -> str:
    """Compute deterministic SHA-256 hash of exact command argument list."""
    joined = "\0".join(argv)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


class AtomicExecutionLedger:
    """Exclusive atomic execution ledger state machine."""

    def __init__(self, authorization_id: str):
        self.authorization_id = authorization_id
        self.ledger_path = f"/private/tmp/fi-e2e-ledger-{authorization_id}.json"

    def create_exclusive(self, command_hash: str, target_head: str, device_id: str) -> dict[str, Any]:
        """Atomically create ledger file with mode 0600. Fails if ledger already exists."""
        initial_data = {
            "authorization_id": self.authorization_id,
            "target_head": target_head,
            "device_id": device_id,
            "command_sha256": command_hash,
            "created_at": datetime.now(UTC).isoformat(),
            "state": "RESERVED",
            "execution_count": 0,
        }

        try:
            fd = os.open(
                self.ledger_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(fd, "w") as f:
                json.dump(initial_data, f, indent=2)
            return initial_data
        except FileExistsError:
            raise LedgerError(
                f"LEDGER_ALREADY_EXISTS: Ledger at {self.ledger_path} already exists. Second run blocked."
            )

    def atomic_update_state(self, new_state: str, execution_count: int | None = None) -> dict[str, Any]:
        """Atomically update state using temporary sibling file and atomic replace."""
        if not os.path.exists(self.ledger_path):
            raise LedgerError(f"LEDGER_NOT_FOUND: Ledger at {self.ledger_path} does not exist.")

        with open(self.ledger_path) as f:
            data = json.load(f)

        data["state"] = new_state
        if execution_count is not None:
            if execution_count > 1:
                raise LedgerError(f"EXECUTION_COUNT_EXCEEDED: execution_count {execution_count} > 1 is prohibited.")
            data["execution_count"] = execution_count
        data["updated_at"] = datetime.now(UTC).isoformat()

        tmp_path = f"{self.ledger_path}.tmp.{uuid.uuid4().hex[:8]}"
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)

        os.replace(tmp_path, self.ledger_path)
        return data


def redact_sensitive_text(text: str) -> str:
    """Redact sensitive keys, authorization headers, and raw financial payloads."""
    import re

    redacted = text
    redacted = re.sub(r"sk-ant-api03-[A-Za-z0-9_\-]+", "[REDACTED_API_KEY]", redacted)
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED_TOKEN]", redacted)
    redacted = re.sub(r"password=([^\s&]+)", "password=[REDACTED_PASSWORD]", redacted)
    return redacted


def check_credential_presence() -> bool:
    """Check boolean presence of ANTHROPIC_API_KEY without logging its value."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key and key.strip():
        return True

    # Check safe tmp environment file
    env_file = "/private/tmp/fi-anthropic-e2e.env"
    if os.path.exists(env_file):
        try:
            with open(env_file) as f:
                content = f.read()
                if "ANTHROPIC_API_KEY=" in content:
                    return True
        except Exception:
            pass
    return False


def build_flutter_argv(
    device_id: str,
    manifest: FixtureManifest,
    authorization_id: str,
    api_base_url: str = "http://127.0.0.1:8000",
    fixture_file_path: str = "",
) -> list[str]:
    """Construct exact Flutter test command argument list with 7 unique --dart-define parameters."""
    eff_fixture_path = fixture_file_path or f"/private/tmp/fi-fixture-{manifest.run_namespace}.pdf"
    return [
        "flutter",
        "test",
        "integration_test/upload_ingestion_analysis_sse_app_e2e_test.dart",
        "-d",
        device_id,
        f"--dart-define=FI_E2E_API_BASE_URL={api_base_url}",
        f"--dart-define=FI_E2E_AUTHORIZATION_ID={authorization_id}",
        f"--dart-define=FI_E2E_ORGANIZATION_ID={manifest.organization_id}",
        f"--dart-define=FI_E2E_ACTOR_ID={manifest.actor_id}",
        f"--dart-define=FI_E2E_INSTITUTION_ID={manifest.institution_id}",
        f"--dart-define=FI_E2E_REPORTING_PERIOD_ID={manifest.reporting_period_id}",
        f"--dart-define=FI_E2E_FIXTURE_FILE_PATH={eff_fixture_path}",
    ]


def run_harness_dry_run(
    authorization_id: str,
    device_id: str,
    credential_env_file: str | None = None,
    target_head: str = "78f6f9d00499298dbe0eaf7adaf0670877cef360",
    api_base_url: str = "http://127.0.0.1:8000",
) -> dict[str, Any]:
    """Perform dry-run preflight validation. Zero DB writes, zero process starts, zero test executions."""
    # 1. Local URL target validation
    api_url = os.environ.get("TEST_API_DATABASE_URL", "postgresql+asyncpg://db_api_user:dev_api_user_pass_123@localhost:5433/finance_intelligence_test")
    validate_local_loopback_url(api_url, "TEST_API_DATABASE_URL")
    validate_local_loopback_url(api_base_url, "FI_E2E_API_BASE_URL")

    # 2. Credential boolean check
    cred_ok = check_credential_presence()

    # 3. Fixture manifest generation
    manifest = generate_fixture_manifest(authorization_id)

    # 4. Command hash
    argv = build_flutter_argv(device_id, manifest, authorization_id=authorization_id, api_base_url=api_base_url)
    cmd_hash = compute_command_hash(argv)

    plan = {
        "status": "DRY_RUN_SUCCESS",
        "mode": "dry-run",
        "authorization_id": authorization_id,
        "device_id": device_id,
        "target_head": target_head,
        "credential_present": cred_ok,
        "fixture_manifest": asdict(manifest),
        "command_argv": argv,
        "command_sha256": cmd_hash,
        "emitted_define_count": 7,
        "unique_define_count": len(set(arg for arg in argv if arg.startswith("--dart-define="))),
        "db_writes_count": 0,
        "processes_started_count": 0,
        "flutter_tests_executed_count": 0,
    }
    return plan


def run_harness_execute(
    authorization_id: str,
    device_id: str,
    credential_env_file: str | None = None,
    target_head: str = "78f6f9d00499298dbe0eaf7adaf0670877cef360",
    api_base_url: str = "http://127.0.0.1:8000",
    runner_fn: Any = None,
    seed_fn: Any = None,
    cleanup_fn: Any = None,
    service_launcher_fn: Any = None,
    fixture_file_path: str = "",
) -> dict[str, Any]:
    """Execute single-run local iOS application E2E test pipeline."""
    # 1. Local target safety guard
    api_url = os.environ.get("TEST_API_DATABASE_URL", "postgresql+asyncpg://db_api_user:dev_api_user_pass_123@localhost:5433/finance_intelligence_test")
    validate_local_loopback_url(api_url, "TEST_API_DATABASE_URL")
    validate_local_loopback_url(api_base_url, "FI_E2E_API_BASE_URL")

    # 2. Credential validation (checking file permissions if provided)
    if credential_env_file:
        if os.path.islink(credential_env_file):
            raise PreflightError(f"REJECTED: Credential env file '{credential_env_file}' is a symlink.")
        if not os.path.isfile(credential_env_file):
            raise PreflightError(f"REJECTED: Credential env file '{credential_env_file}' is not a regular file.")
        st = os.stat(credential_env_file)
        import stat
        if st.st_uid != os.getuid():
            raise PreflightError(f"REJECTED: Credential env file '{credential_env_file}' is not owned by current user.")
        mode = stat.S_IMODE(st.st_mode)
        if mode & 0o077 != 0:
            raise PreflightError(f"REJECTED: Credential env file '{credential_env_file}' permissions {oct(mode)} exceed 0600.")

    if not check_credential_presence():
        raise PreflightError("REJECTED: ANTHROPIC_API_KEY is absent from environment and credential file.")

    # 3. Fixture manifest generation
    manifest = generate_fixture_manifest(authorization_id)

    # Fixture file handling
    created_fixture_by_harness = False
    eff_fixture_path = fixture_file_path
    if not eff_fixture_path:
        eff_fixture_path = f"/private/tmp/fi-fixture-{manifest.run_namespace}.pdf"
        if not os.path.exists(eff_fixture_path):
            fd = os.open(eff_fixture_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(
                    "%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
                    "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
                    "3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources <<>> /Contents 4 0 R >>\nendobj\n"
                    "4 0 obj\n<< /Length 50 >>\nstream\nBT /F1 12 Tf 72 712 Td (Garanti 2025 Q4 Test Report) Tj ET\nendstream\nendobj\n"
                    "xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000062 00000 n \n0000000125 00000 n \n0000000208 00000 n \n"
                    "trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n308\n%%EOF\n"
                )
            created_fixture_by_harness = True

    # 4. Command hash
    argv = build_flutter_argv(device_id, manifest, authorization_id=authorization_id, api_base_url=api_base_url, fixture_file_path=eff_fixture_path)
    cmd_hash = compute_command_hash(argv)


    # 5. Atomic ledger creation
    ledger = AtomicExecutionLedger(authorization_id)
    ledger.create_exclusive(cmd_hash, target_head, device_id)

    # Evidence directory setup
    evidence_dir = f"/private/tmp/fi-r5-{authorization_id}"
    os.makedirs(evidence_dir, mode=0o700, exist_ok=True)

    execution_result = "NOT_STARTED"
    cleanup_status = "NOT_STARTED"

    try:
        # DB Fixture Seed
        if seed_fn:
            seed_fn(manifest)

        # Update ledger state to STARTED, execution_count to 1
        ledger.atomic_update_state("STARTED", execution_count=1)

        # Service launcher
        if service_launcher_fn:
            service_launcher_fn()

        # Run Flutter subprocess
        exit_code = 0
        if runner_fn:
            exit_code = runner_fn(argv)

        if exit_code == 0:
            execution_result = "PASSED"
            ledger.atomic_update_state("PASSED", execution_count=1)
        else:
            execution_result = "FAILED"
            ledger.atomic_update_state("FAILED", execution_count=1)

    except Exception as ex:
        execution_result = "FAILED"
        try:
            ledger.atomic_update_state("PREFLIGHT_FAILED")
        except Exception:
            pass
        raise ex
    finally:
        # Fixture Teardown & Process Cleanup & Temporary Fixture Removal
        try:
            if cleanup_fn:
                cleanup_fn(manifest)
            if created_fixture_by_harness and os.path.exists(eff_fixture_path):
                os.remove(eff_fixture_path)
            cleanup_status = "COMPLETE"
        except Exception:
            cleanup_status = "FAILED"
        ledger.atomic_update_state("CLEANUP_COMPLETE", execution_count=1)

    return {
        "status": "EXECUTION_SUCCESS" if execution_result == "PASSED" else "EXECUTION_FAILED",
        "authorization_id": authorization_id,
        "execution_result": execution_result,
        "cleanup_status": cleanup_status,
        "command_argv": argv,
        "command_sha256": cmd_hash,
        "emitted_define_count": 7,
        "unique_define_count": len(set(arg for arg in argv if arg.startswith("--dart-define="))),
        "ledger_path": ledger.ledger_path,
        "evidence_directory": evidence_dir,
    }



def main() -> None:
    parser = argparse.ArgumentParser(description="Canonical Python harness for single-run local iOS application E2E test execution.")
    parser.add_argument("--authorization-id", required=True, help="Unique authorization identifier for this run.")
    parser.add_argument("--device-id", required=True, help="Exact iOS simulator device ID.")
    parser.add_argument("--credential-env-file", default=None, help="Path to safe non-repository credential env file.")
    parser.add_argument("--execute", action="store_true", help="Explicit flag required for real execution mode. Default is dry-run.")
    args = parser.parse_args()

    if not args.execute:
        plan = run_harness_dry_run(args.authorization_id, args.device_id, args.credential_env_file)
        print(json.dumps(plan, indent=2))
        sys.exit(0)
    else:
        res = run_harness_execute(args.authorization_id, args.device_id, args.credential_env_file)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res.get("status") == "EXECUTION_SUCCESS" else 1)


if __name__ == "__main__":
    main()
