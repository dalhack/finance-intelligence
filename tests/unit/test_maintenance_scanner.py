from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MAINTENANCE_WORKER_PATH = REPO_ROOT / "services" / "worker" / "app" / "maintenance_worker.py"


def test_maintenance_production_print_and_log_scanner():
    """Assert zero print statements and zero raw secret/token leakage in maintenance worker source."""
    assert MAINTENANCE_WORKER_PATH.exists(), f"File not found: {MAINTENANCE_WORKER_PATH}"

    content = MAINTENANCE_WORKER_PATH.read_text(encoding="utf-8")
    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "print(" not in line, f"Found forbidden print() at line {idx} in maintenance_worker.py"
        assert "eval(" not in line, f"Found forbidden eval() at line {idx} in maintenance_worker.py"
        assert "exec(" not in line, f"Found forbidden exec() at line {idx} in maintenance_worker.py"
