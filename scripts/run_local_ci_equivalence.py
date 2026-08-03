import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_cmd(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> tuple[int, str]:
    """Execute command args array without shell=True and return (exit_code, output)."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    full_env["PYTHONPATH"] = str(PROJECT_ROOT)

    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd or PROJECT_ROOT),
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout.strip()
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def main() -> None:
    python_bin = sys.executable
    pytest_bin = str(PROJECT_ROOT / ".venv" / "bin" / "pytest")
    ruff_bin = str(PROJECT_ROOT / ".venv" / "bin" / "ruff")
    mypy_bin = str(PROJECT_ROOT / ".venv" / "bin" / "mypy")

    if not Path(pytest_bin).exists():
        pytest_bin = "pytest"
    if not Path(ruff_bin).exists():
        ruff_bin = "ruff"
    if not Path(mypy_bin).exists():
        mypy_bin = "mypy"

    mobile_dir = PROJECT_ROOT / "apps" / "mobile"

    postgres_env = {
        "TEST_OWNER_DATABASE_URL": "postgresql+asyncpg://db_owner:owner_pass@localhost:5432/finance_intelligence_test",
        "TEST_BOOTSTRAP_DATABASE_URL": "postgresql+asyncpg://db_bootstrap:bootstrap_pass@localhost:5432/finance_intelligence_test",
        "TEST_API_DATABASE_URL": "postgresql+asyncpg://db_api_user:api_pass@localhost:5432/finance_intelligence_test",
        "TEST_WORKER_DATABASE_URL": "postgresql+asyncpg://db_ingestion_worker:worker_pass@localhost:5432/finance_intelligence_test",
        "TEST_ROUNDTRIP_DATABASE_URL": "postgresql+asyncpg://db_owner:owner_pass@localhost:5432/finance_intelligence_roundtrip_test",
        "TEST_MAINTENANCE_DATABASE_URL": "postgresql+asyncpg://db_maintenance_worker:dev_maintenance_pass_123@localhost:5432/finance_intelligence_test",
    }

    gates_to_run = [
        {
            "gateId": "LOCAL_BOUNDARY_SECRET_GATE",
            "args": [pytest_bin, "tests/unit/test_secret_scanner.py"],
            "cwd": PROJECT_ROOT,
        },
        {
            "gateId": "LOCAL_PYTHON_RUFF_LINT_GATE",
            "args": [ruff_bin, "check", "."],
            "cwd": PROJECT_ROOT,
        },
        {
            "gateId": "LOCAL_PYTHON_RUFF_FORMAT_GATE",
            "args": [ruff_bin, "format", "--check", "."],
            "cwd": PROJECT_ROOT,
        },
        {
            "gateId": "LOCAL_PYTHON_MYPY_GATE",
            "args": [mypy_bin, "."],
            "cwd": PROJECT_ROOT,
        },
        {
            "gateId": "LOCAL_PYTHON_UNIT_GATE",
            "args": [pytest_bin, "tests/unit"],
            "cwd": PROJECT_ROOT,
        },
        {
            "gateId": "LOCAL_POSTGRES_INTEGRATION_GATE",
            "args": [pytest_bin, "tests/integration"],
            "cwd": PROJECT_ROOT,
            "env": postgres_env,
        },
        {
            "gateId": "LOCAL_FLUTTER_FORMAT_GATE",
            "args": ["dart", "format", "--output=none", "--set-exit-if-changed", "."],
            "cwd": mobile_dir,
        },
        {
            "gateId": "LOCAL_FLUTTER_ANALYZE_GATE",
            "args": ["flutter", "analyze", "--no-fatal-infos"],
            "cwd": mobile_dir,
        },
        {
            "gateId": "LOCAL_FLUTTER_MACHINE_TEST_GATE",
            "args": ["flutter", "test"],
            "cwd": mobile_dir,
        },
    ]

    results: list[dict[str, Any]] = []
    all_passed = True

    for g in gates_to_run:
        start_t = time.time()
        code, out = run_cmd(g["args"], cwd=g.get("cwd"), env=g.get("env"))
        elapsed = round(time.time() - start_t, 2)
        status = "PASS" if code == 0 else "FAIL"
        if code != 0:
            all_passed = False

        results.append(
            {
                "gateId": g["gateId"],
                "command": " ".join(g["args"]),
                "exitCode": code,
                "durationSeconds": elapsed,
                "status": status,
            }
        )

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": sys.platform,
        "pythonVersion": sys.version.split()[0],
        "allPassed": all_passed,
        "gates": results,
    }

    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
