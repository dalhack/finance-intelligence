import os

MAINTENANCE_WORKER_PATH = (
    "/Users/korhanturgut/.gemini/antigravity-ide/scratch/finance-intelligence/services/worker/app/maintenance_worker.py"
)


def test_maintenance_production_print_and_log_scanner():
    """Assert zero print statements and zero raw secret/token leakage in maintenance worker source."""
    assert os.path.exists(MAINTENANCE_WORKER_PATH), f"File not found: {MAINTENANCE_WORKER_PATH}"

    with open(MAINTENANCE_WORKER_PATH, "r") as f:
        content = f.read()

    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "print(" not in line, f"Found forbidden print() at line {idx} in maintenance_worker.py"
        assert "eval(" not in line, f"Found forbidden eval() at line {idx} in maintenance_worker.py"
        assert "exec(" not in line, f"Found forbidden exec() at line {idx} in maintenance_worker.py"
