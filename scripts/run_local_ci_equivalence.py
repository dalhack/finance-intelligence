import json
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_cmd(cmd_list, cwd=None, env=None):
    proc = subprocess.run(
        cmd_list,
        cwd=cwd or PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = proc.stdout + "\n" + proc.stderr
    if proc.returncode != 0:
        print(f"--- GATE FAILED: {' '.join(cmd_list)} ---\n{output}", file=sys.stderr)
    return proc.returncode, output


def main():
    pytest_bin = str(PROJECT_ROOT / ".venv" / "bin" / "pytest")
    ruff_bin = str(PROJECT_ROOT / ".venv" / "bin" / "ruff")
    mypy_bin = str(PROJECT_ROOT / ".venv" / "bin" / "mypy")

    gates_to_run = [
        {
            "gateId": "LOCAL_BOUNDARY_SECRET_GATE",
            "args": [pytest_bin, "tests/unit/test_secret_scanner.py"],
        },
        {
            "gateId": "LOCAL_PYTHON_RUFF_LINT_GATE",
            "args": [ruff_bin, "check", ".", "--extend-exclude=apps/mobile/ios/Flutter/ephemeral"],
        },
        {
            "gateId": "LOCAL_PYTHON_RUFF_FORMAT_GATE",
            "args": [ruff_bin, "format", "--check", ".", "--extend-exclude=apps/mobile/ios/Flutter/ephemeral"],
        },
        {
            "gateId": "LOCAL_PYTHON_MYPY_GATE",
            "args": [mypy_bin, "."],
        },
        {
            "gateId": "LOCAL_PYTHON_UNIT_GATE",
            "args": [pytest_bin, "tests/unit"],
        },
        {
            "gateId": "LOCAL_POSTGRES_INTEGRATION_GATE",
            "args": [pytest_bin, "tests/integration", "services/api/tests/integration", "-m", "not live_acceptance"],
            "env": {
                "PYTHONPATH": ".:services/api",
                "CI": "true",
                "TEST_BOOTSTRAP_PASSWORD": "bootstrap_pass",
                "TEST_API_PASSWORD": "api_pass",
                "TEST_WORKER_PASSWORD": "worker_pass",
                "TEST_MAINTENANCE_PASSWORD": "dev_maintenance_pass_123",
                "TEST_OWNER_DATABASE_URL": "postgresql+asyncpg://db_owner:owner_pass@localhost:5432/finance_intelligence_test",
                "TEST_BOOTSTRAP_DATABASE_URL": "postgresql+asyncpg://db_bootstrap:bootstrap_pass@localhost:5432/finance_intelligence_test",
                "TEST_API_DATABASE_URL": "postgresql+asyncpg://db_api_user:api_pass@localhost:5432/finance_intelligence_test",
                "TEST_WORKER_DATABASE_URL": "postgresql+asyncpg://db_ingestion_worker:worker_pass@localhost:5432/finance_intelligence_test",
                "TEST_ROUNDTRIP_DATABASE_URL": "postgresql+asyncpg://db_owner:owner_pass@localhost:5432/finance_intelligence_roundtrip_test",
                "TEST_MAINTENANCE_DATABASE_URL": "postgresql+asyncpg://db_maintenance_worker:dev_maintenance_pass_123@localhost:5432/finance_intelligence_test",
            },
        },
        {
            "gateId": "LOCAL_FLUTTER_FORMAT_GATE",
            "cwd": PROJECT_ROOT / "apps" / "mobile",
            "args": ["dart", "format", "--output=none", "--set-exit-if-changed", "."],
        },
        {
            "gateId": "LOCAL_FLUTTER_ANALYZE_GATE",
            "cwd": PROJECT_ROOT / "apps" / "mobile",
            "args": ["flutter", "analyze"],
        },
        {
            "gateId": "LOCAL_FLUTTER_MACHINE_TEST_GATE",
            "cwd": PROJECT_ROOT / "apps" / "mobile",
            "args": ["flutter", "test"],
        },
    ]

    gate_results = []
    all_passed = True

    for g in gates_to_run:
        start_t = time.time()
        code, _out = run_cmd(g["args"], cwd=g.get("cwd"), env=g.get("env"))
        elapsed = round(time.time() - start_t, 2)
        status = "PASS" if code == 0 else "FAIL"
        if code != 0:
            all_passed = False

        gate_results.append(
            {
                "gateId": g["gateId"],
                "command": " ".join([str(a) for a in g["args"]]),
                "exitCode": code,
                "durationSeconds": elapsed,
                "status": status,
            }
        )

    summary_payload = {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": platform.system().lower(),
        "pythonVersion": platform.python_version(),
        "allPassed": all_passed,
        "gates": gate_results,
    }

    print(json.dumps(summary_payload, indent=2))
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
