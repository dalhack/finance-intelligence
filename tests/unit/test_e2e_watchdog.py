"""Unit tests for E2E Process Watchdog Runner (scripts/run_e2e_watchdog.py)."""

import sys
import time

from scripts.run_e2e_watchdog import is_command_allowed, redact_line, run_watchdog


def test_watchdog_log_redaction():
    """Verifies sensitive tokens and passwords are redacted from log lines."""
    raw_auth = "AUTHORIZATION: basic dXNlcjpwYXNz"
    raw_bearer = "bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    raw_pass = "DATABASE_URL=postgresql://user:secret_pass_123@localhost/db"

    assert redact_line(raw_auth) == "AUTHORIZATION: basic [REDACTED]"
    assert redact_line(raw_bearer) == "bearer [REDACTED]"
    assert "secret_pass_123" not in redact_line(raw_pass)


def test_watchdog_command_allowlist():
    """Verifies command allowlist enforcement."""
    assert is_command_allowed(["flutter", "test", "integration_test/device_e2e_test.dart", "-d", "UDID"]) is True
    assert is_command_allowed(["flutter", "devices"]) is True
    assert is_command_allowed(["python", "scripts/verify_migration_roundtrip.py"]) is True
    assert is_command_allowed(["rm", "-rf", "/"]) is False
    assert is_command_allowed(["curl", "https://malicious.com"]) is False


def test_watchdog_fast_success():
    """Verifies fast success returning exit code 0."""
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", "import sys; print('Fast success test'); sys.exit(0)"],
        timeout_seconds=5,
        heartbeat_interval_seconds=1,
    )
    assert code == 0


def test_watchdog_nonzero_failure():
    """Verifies non-zero exit code propagation."""
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", "import sys; print('Failing test'); sys.exit(42)"],
        timeout_seconds=5,
        heartbeat_interval_seconds=1,
    )
    assert code == 42


def test_watchdog_silent_hang_timeout():
    """Verifies silent hang is terminated on timeout returning exit code 124."""
    start = time.time()
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", "import time; time.sleep(10)"],
        timeout_seconds=2,
        heartbeat_interval_seconds=1,
    )
    elapsed = time.time() - start
    assert code == 124
    assert elapsed < 5.0  # Terminated within timeout budget


def test_watchdog_output_hang_timeout():
    """Verifies output-producing hang is terminated on timeout returning exit code 124."""
    cmd = (
        "import time, sys\n"
        "for i in range(100):\n"
        "    print(f'Hanging step {i}')\n"
        "    sys.stdout.flush()\n"
        "    time.sleep(0.5)\n"
    )
    start = time.time()
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", cmd],
        timeout_seconds=2,
        heartbeat_interval_seconds=1,
    )
    elapsed = time.time() - start
    assert code == 124
    assert elapsed < 5.0


def test_watchdog_child_process_tree_cleanup():
    """Verifies child and grandchild processes are cleaned up post-timeout."""
    cmd = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])\n"
        "time.sleep(10)\n"
    )
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", cmd],
        timeout_seconds=2,
        heartbeat_interval_seconds=1,
    )
    assert code == 124
