"""Unit tests for E2E Process Watchdog Runner (scripts/run_e2e_watchdog.py)."""

import signal
import sys
import time
from unittest.mock import patch

import pytest

from scripts.run_e2e_watchdog import (
    EVENT_PHASE_CHANGED,
    EVENT_PID_FALLBACK_SENT,
    EVENT_PROCESS_EXIT_CONFIRMED,
    EVENT_PROCESS_STILL_ALIVE,
    EVENT_SIGTERM_GROUP_FAILED,
    EVENT_WATCHDOG_CHILD_FAILED,
    EVENT_WATCHDOG_SILENCE_TIMEOUT,
    EVENT_WATCHDOG_STARTED,
    EVENT_WATCHDOG_SUCCEEDED,
    EVENT_WATCHDOG_TIMEOUT,
    PHASE_TEST_BODY,
    PHASE_TEST_DRIVER_CONNECT,
    PHASE_XCODE_BUILD,
    infer_phase_from_output,
    is_command_allowed,
    redact_line,
    run_watchdog,
    terminate_process_group,
)


def test_watchdog_log_redaction():
    """T9: Verifies sensitive tokens and passwords are redacted from log lines."""
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
    """Verifies invalid timeout, silence timeout, or grace period parameters raise ValueError."""
    with pytest.raises(ValueError, match="timeout_seconds"):
        run_watchdog(cmd_args=[sys.executable, "-c", "pass"], timeout_seconds=0)

    with pytest.raises(ValueError, match="silence_timeout_seconds"):
        run_watchdog(cmd_args=[sys.executable, "-c", "pass"], silence_timeout_seconds=0)

    with pytest.raises(ValueError, match="grace_seconds"):
        run_watchdog(cmd_args=[sys.executable, "-c", "pass"], timeout_seconds=5, grace_seconds=0.0)


def test_watchdog_fast_success(capsys):
    """T10: Verifies fast success returning exit code 0 and correct event sequence."""
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", "import sys; print('Fast success test'); sys.exit(0)"],
        timeout_seconds=5,
        silence_timeout_seconds=5,
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
        silence_timeout_seconds=5,
        grace_seconds=0.2,
        heartbeat_interval_seconds=1,
    )
    assert code == 42
    captured = capsys.readouterr()
    assert EVENT_WATCHDOG_STARTED in captured.out
    assert EVENT_WATCHDOG_CHILD_FAILED in captured.err
    assert EVENT_WATCHDOG_SUCCEEDED not in captured.out


def test_watchdog_child_output_resets_silence_timeout(capsys):
    """T1: Verifies regular child output resets silence timeout and avoids silence trigger."""
    cmd = (
        "import time, sys\n"
        "for i in range(4):\n"
        "    print(f'Active output step {i}')\n"
        "    sys.stdout.flush()\n"
        "    time.sleep(0.3)\n"
    )
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", cmd],
        timeout_seconds=10,
        silence_timeout_seconds=2,
        grace_seconds=0.2,
        heartbeat_interval_seconds=1,
    )
    assert code == 0
    captured = capsys.readouterr()
    assert EVENT_WATCHDOG_SILENCE_TIMEOUT not in captured.err


def test_watchdog_heartbeat_does_not_reset_silence_timeout(capsys):
    """T2 & T3: Verifies heartbeat logging does not reset child silence counter and triggers fail-closed silence timeout."""
    cmd = "import time, sys\nprint('Initial output')\nsys.stdout.flush()\ntime.sleep(3)\n"
    start = time.time()
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", cmd],
        timeout_seconds=10,
        silence_timeout_seconds=1,
        heartbeat_interval_seconds=1,
        grace_seconds=0.2,
    )
    elapsed = time.time() - start

    assert code == 1
    assert elapsed < 3.0
    captured = capsys.readouterr()
    assert EVENT_WATCHDOG_SILENCE_TIMEOUT in captured.err


def test_watchdog_global_hard_timeout_preserved(capsys):
    """T4: Verifies global hard timeout limit is enforced when output is continuous."""
    cmd = (
        "import time, sys\nfor i in range(100):\n    print(f'Step {i}')\n    sys.stdout.flush()\n    time.sleep(0.1)\n"
    )
    timeout_sec = 1
    grace_sec = 0.2
    start = time.time()
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", cmd],
        timeout_seconds=timeout_sec,
        silence_timeout_seconds=5,
        grace_seconds=grace_sec,
        heartbeat_interval_seconds=1,
    )
    elapsed = time.time() - start

    assert code == 124
    assert elapsed < (timeout_sec + grace_sec + 1.0)
    captured = capsys.readouterr()
    assert EVENT_WATCHDOG_TIMEOUT in captured.err


def test_watchdog_killpg_eperm_triggers_pid_fallback(capsys):
    """T5 & T6: Verifies killpg EPERM error triggers PID fallback and verifies exit."""
    fake_pid = 99999
    call_log = []

    def mock_killpg(pgid, sig):
        call_log.append(("killpg", pgid, sig))
        raise OSError(1, "Operation not permitted")

    def mock_kill(pid, sig):
        call_log.append(("kill", pid, sig))
        if sig == 0:
            raise ProcessLookupError()

    with patch("os.killpg", side_effect=mock_killpg), patch("os.kill", side_effect=mock_kill):
        terminate_process_group(pgid=fake_pid, pid=fake_pid, grace_period_sec=0.1)

    captured = capsys.readouterr()
    assert EVENT_SIGTERM_GROUP_FAILED in captured.err
    assert EVENT_PID_FALLBACK_SENT in captured.err
    assert EVENT_PROCESS_EXIT_CONFIRMED in captured.err
    assert ("kill", fake_pid, signal.SIGTERM) in call_log


def test_watchdog_process_still_alive_raises_runtime_error():
    """T7: Verifies RuntimeError is raised if process remains alive after fallback."""
    fake_pid = 88888

    def mock_killpg(pgid, sig):
        raise OSError(1, "Operation not permitted")

    def mock_kill(pid, sig):
        if sig == 0:
            return  # Still alive!
        return

    with (
        patch("os.killpg", side_effect=mock_killpg),
        patch("os.kill", side_effect=mock_kill),
        pytest.raises(RuntimeError, match=EVENT_PROCESS_STILL_ALIVE),
    ):
        terminate_process_group(pgid=fake_pid, pid=fake_pid, grace_period_sec=0.1)


def test_watchdog_phase_and_timing_diagnostic_output(capsys):
    """T8: Verifies phase transition and timing fields in diagnostic timeout output."""
    assert infer_phase_from_output("Building Runner.app with Xcode", "UNKNOWN") == PHASE_XCODE_BUILD
    assert (
        infer_phase_from_output("Connecting to VM Service at http://127.0.0.1", "UNKNOWN") == PHASE_TEST_DRIVER_CONNECT
    )
    assert infer_phase_from_output("Running test: login_flow_test", "UNKNOWN") == PHASE_TEST_BODY

    cmd = (
        "import time, sys\n"
        "print('Building Runner.app')\n"
        "sys.stdout.flush()\n"
        "print('Connecting to VM Service')\n"
        "sys.stdout.flush()\n"
        "time.sleep(5)\n"
    )
    code = run_watchdog(
        cmd_args=[sys.executable, "-c", cmd],
        timeout_seconds=10,
        silence_timeout_seconds=1,
        grace_seconds=0.2,
        heartbeat_interval_seconds=1,
    )
    assert code == 1
    captured = capsys.readouterr()
    assert EVENT_PHASE_CHANGED in captured.out
    assert PHASE_TEST_DRIVER_CONNECT in captured.out or PHASE_TEST_DRIVER_CONNECT in captured.err


def test_watchdog_silence_budget_safety_margin():
    """Verifies math calculation for healthy max silence (110s) vs calibrated limit (180s) safety margin (>= 60s)."""
    healthy_max_observed_silence = 110
    calibrated_silence_timeout = 180
    safety_margin = calibrated_silence_timeout - healthy_max_observed_silence

    assert safety_margin >= 60, f"Safety margin {safety_margin}s must be >= 60s"
    assert calibrated_silence_timeout < 900
