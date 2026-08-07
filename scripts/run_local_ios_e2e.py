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


def build_flutter_argv(device_id: str, manifest: FixtureManifest) -> list[str]:
    """Construct exact Flutter test command argument list without using shell."""
    return [
        "flutter",
        "test",
        "integration_test/upload_ingestion_analysis_sse_app_e2e_test.dart",
        "-d",
        device_id,
        f"--dart-define=FI_E2E_AUTHORIZATION_ID={manifest.run_namespace}",
        f"--dart-define=FI_E2E_ORGANIZATION_ID={manifest.organization_id}",
        f"--dart-define=FI_E2E_INSTITUTION_ID={manifest.institution_id}",
        f"--dart-define=FI_E2E_REPORTING_PERIOD_ID={manifest.reporting_period_id}",
    ]


def run_harness_dry_run(authorization_id: str, device_id: str, target_head: str = "596d85055cff352e70085d7490427be7d2f08a69") -> dict[str, Any]:
    """Perform dry-run preflight validation. Zero DB writes, zero process starts, zero test executions."""
    # 1. Local URL target validation
    api_url = os.environ.get("TEST_API_DATABASE_URL", "postgresql+asyncpg://db_api_user:dev_api_user_pass_123@localhost:5433/finance_intelligence_test")
    validate_local_loopback_url(api_url, "TEST_API_DATABASE_URL")

    # 2. Credential boolean check
    cred_ok = check_credential_presence()

    # 3. Fixture manifest generation
    manifest = generate_fixture_manifest(authorization_id)

    # 4. Command hash
    argv = build_flutter_argv(device_id, manifest)
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
        "db_writes_count": 0,
        "processes_started_count": 0,
        "flutter_tests_executed_count": 0,
    }
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Canonical Python harness for single-run local iOS application E2E test execution.")
    parser.add_argument("--authorization-id", required=True, help="Unique authorization identifier for this run.")
    parser.add_argument("--device-id", required=True, help="Exact iOS simulator device ID.")
    parser.add_argument("--execute", action="store_true", help="Explicit flag required for real execution mode. Default is dry-run.")
    args = parser.parse_args()

    if not args.execute:
        plan = run_harness_dry_run(args.authorization_id, args.device_id)
        print(json.dumps(plan, indent=2))
        sys.exit(0)
    else:
        print(json.dumps({"status": "REAL_EXECUTION_REQUIRES_AUTHORIZED_ORCHESTRATION_TURNS", "mode": "execute"}, indent=2))
        sys.exit(0)


if __name__ == "__main__":
    main()
