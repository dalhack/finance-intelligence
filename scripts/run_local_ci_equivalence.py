import json
import subprocess
import sys
import time
from typing import Any


def run_cmd(cmd: str, cwd: str | None = None) -> tuple[int, str]:
    """Execute command and return (exit_code, output)."""
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd or "/Users/korhanturgut/.gemini/antigravity-ide/scratch/finance-intelligence",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout.strip()
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def main() -> None:
    project_root = "/Users/korhanturgut/.gemini/antigravity-ide/scratch/finance-intelligence"
    results: list[dict[str, Any]] = []

    gates_to_run = [
        {
            "gateId": "LOCAL_BOUNDARY_SECRET_GATE",
            "cmd": "PYTHONPATH=. .venv/bin/pytest tests/unit/test_secret_scanner.py",
        },
        {
            "gateId": "LOCAL_PYTHON_STATIC_GATE",
            "cmd": ".venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy .",
        },
        {
            "gateId": "LOCAL_PYTHON_UNIT_GATE",
            "cmd": "PYTHONPATH=. .venv/bin/pytest tests/unit",
        },
        {
            "gateId": "LOCAL_POSTGRES_INTEGRATION_GATE",
            "cmd": 'TEST_OWNER_DATABASE_URL="postgresql+asyncpg://db_owner:owner_pass@localhost:5432/finance_intelligence_test" TEST_BOOTSTRAP_DATABASE_URL="postgresql+asyncpg://db_bootstrap:bootstrap_pass@localhost:5432/finance_intelligence_test" TEST_API_DATABASE_URL="postgresql+asyncpg://db_api_user:api_pass@localhost:5432/finance_intelligence_test" TEST_WORKER_DATABASE_URL="postgresql+asyncpg://db_ingestion_worker:worker_pass@localhost:5432/finance_intelligence_test" TEST_ROUNDTRIP_DATABASE_URL="postgresql+asyncpg://db_owner:owner_pass@localhost:5432/finance_intelligence_roundtrip_test" TEST_MAINTENANCE_DATABASE_URL="postgresql+asyncpg://db_maintenance_worker:dev_maintenance_pass_123@localhost:5432/finance_intelligence_test" PYTHONPATH=. .venv/bin/pytest tests/integration',
        },
        {
            "gateId": "LOCAL_FLUTTER_STATIC_GATE",
            "cmd": "dart format --output=none --set-exit-if-changed . && flutter analyze --no-fatal-infos",
            "cwd": f"{project_root}/apps/mobile",
        },
        {
            "gateId": "LOCAL_FLUTTER_MACHINE_TEST_GATE",
            "cmd": "flutter test",
            "cwd": f"{project_root}/apps/mobile",
        },
    ]

    all_passed = True
    for g in gates_to_run:
        code, _out = run_cmd(g["cmd"], cwd=g.get("cwd"))
        status = "PASS" if code == 0 else "FAIL"
        if code != 0:
            all_passed = False
        results.append(
            {
                "gateId": g["gateId"],
                "command": g["cmd"],
                "exitCode": code,
                "status": status,
            }
        )

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "allPassed": all_passed,
        "gates": results,
    }
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
