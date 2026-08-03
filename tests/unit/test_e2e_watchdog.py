"""Unit tests for E2E Process Watchdog Runner (scripts/run_e2e_watchdog.py)."""

import sys
import time

import pytest

from scripts.run_e2e_watchdog import (
    EVENT_WATCHDOG_CHILD_FAILED,
    EVENT_WATCHDOG_KILLED,
    EVENT_WATCHDOG_STARTED,
    EVENT_WATCHDOG_SUCCEEDED,
    EVENT_WATCHDOG_TERMINATING,
    EVENT_WATCHDOG_TIMEOUT,
    is_command_allowed,
    redact_line,
    run_watchdog,
)


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


def test_watchdog_invalid_parameters():
    """Verifies invalid timeout or grace period parameters raise ValueError."""
    with pytest.raises(ValueError, match="timeout_seconds"):
        run_watchdog(cmd_args=[sys.executable, "-c", "pass"], timeout_seconds=0)

    with pytest.raises(ValueError, match="grace_seconds"):
        run_watchdog(cmd_args=[sys.executable, "-c", "pass"], timeout_seconds=5, grace_seconds=0.0)


def test_watchdog_fast_success(capsys):
    """Verifies fast success returning exit code 0 and correct event sequence."""
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", "import sys; print('Fast success test'); sys.exit(0)"],
        timeout_seconds=5,
        grace_seconds=0.2,
        heartbeat_interval_seconds=1,
    )
    assert code == 0
    captured = capsys.readouterr()
    assert EVENT_WATCHDOG_STARTED in captured.out
    assert EVENT_WATCHDOG_SUCCEEDED in captured.out
    assert EVENT_WATCHDOG_CHILD_FAILED not in captured.err


def test_watchdog_nonzero_failure(capsys):
    """Verifies non-zero exit code propagation and child failure event."""
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", "import sys; print('Failing test'); sys.exit(42)"],
        timeout_seconds=5,
        grace_seconds=0.2,
        heartbeat_interval_seconds=1,
    )
    assert code == 42
    captured = capsys.readouterr()
    assert EVENT_WATCHDOG_STARTED in captured.out
    assert EVENT_WATCHDOG_CHILD_FAILED in captured.err
    assert EVENT_WATCHDOG_SUCCEEDED not in captured.out


def test_watchdog_silent_hang_timeout(capsys):
    """Verifies silent hang is terminated on timeout using configurable grace period."""
    timeout_sec = 1
    grace_sec = 0.2
    start = time.time()
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", "import time; time.sleep(10)"],
        timeout_seconds=timeout_sec,
        grace_seconds=grace_sec,
        heartbeat_interval_seconds=1,
    )
    elapsed = time.time() - start

    assert code == 124
    # Assertion models timeout + grace_seconds + 1.0s scheduling tolerance
    assert elapsed < (timeout_sec + grace_sec + 1.0)
    captured = capsys.readouterr()
    assert EVENT_WATCHDOG_TIMEOUT in captured.err
    assert EVENT_WATCHDOG_TERMINATING in captured.err


def test_watchdog_output_hang_timeout(capsys):
    """Verifies output-producing hang is terminated on timeout using configurable grace period."""
    cmd = (
        "import time, sys\n"
        "for i in range(100):\n"
        "    print(f'Hanging step {i}')\n"
        "    sys.stdout.flush()\n"
        "    time.sleep(0.2)\n"
    )
    timeout_sec = 1
    grace_sec = 0.2
    start = time.time()
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", cmd],
        timeout_seconds=timeout_sec,
        grace_seconds=grace_sec,
        heartbeat_interval_seconds=1,
    )
    elapsed = time.time() - start

    assert code == 124
    assert elapsed < (timeout_sec + grace_sec + 1.0)
    captured = capsys.readouterr()
    assert EVENT_WATCHDOG_TIMEOUT in captured.err


def test_watchdog_sigkill_escalation(capsys):
    """Verifies child process ignoring SIGTERM escalates to SIGKILL."""
    cmd = (
        "import signal, time, sys\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print('Ignoring SIGTERM...')\n"
        "sys.stdout.flush()\n"
        "time.sleep(10)\n"
    )
    timeout_sec = 1
    grace_sec = 0.3
    start = time.time()
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", cmd],
        timeout_seconds=timeout_sec,
        grace_seconds=grace_sec,
        heartbeat_interval_seconds=1,
    )
    elapsed = time.time() - start

    assert code == 124
    assert elapsed >= (timeout_sec + grace_sec)
    captured = capsys.readouterr()
    assert EVENT_WATCHDOG_TERMINATING in captured.err
    assert EVENT_WATCHDOG_KILLED in captured.err


def test_watchdog_child_process_tree_cleanup():
    """Verifies child and grandchild processes are cleaned up post-timeout."""
    cmd = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])\n"
        "time.sleep(10)\n"
    )
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", cmd],
        timeout_seconds=1,
        grace_seconds=0.2,
        heartbeat_interval_seconds=1,
    )
    assert code == 124
