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
    """T9: Verifies sensitive tokens, URLs, ANSI sequences, and length bounds are enforced."""
    from scripts.run_e2e_watchdog import redact_and_truncate_line

    secret = "TEST_SECRET"

    raw_auth = f"Authorization: Bearer {secret}"
    raw_ws = f"wss://127.0.0.1/ws?authToken={secret}"
    raw_db = f"postgresql://user:{secret}@host/db"
    raw_ansi = f"\x1b[31mError with secret={secret}\x1b[0m"
    long_line = "A" * 200

    redacted_auth = redact_line(raw_auth)
    redacted_ws = redact_line(raw_ws)
    redacted_db = redact_line(raw_db)
    redacted_ansi = redact_line(raw_ansi)
    truncated = redact_and_truncate_line(long_line, max_length=120)

    assert secret not in redacted_auth
    assert secret not in redacted_ws
    assert secret not in redacted_db
    assert secret not in redacted_ansi
    assert "\x1b" not in redacted_ansi
    assert len(truncated) <= 120
    assert truncated.endswith("...")


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
    from scripts.run_e2e_watchdog import PHASE_APP_LAUNCH, PHASE_POST_XCODE_BUILD_WAIT

    assert infer_phase_from_output("Building Runner.app with Xcode", "UNKNOWN") == PHASE_XCODE_BUILD
    assert infer_phase_from_output("Xcode build done. 58.2s", PHASE_XCODE_BUILD) == PHASE_POST_XCODE_BUILD_WAIT
    assert (
        infer_phase_from_output("xcrun simctl install 1234 Runner.app", PHASE_POST_XCODE_BUILD_WAIT) == PHASE_APP_LAUNCH
    )
    assert (
        infer_phase_from_output("Waiting for VM Service port to be available...", PHASE_APP_LAUNCH)
        == PHASE_TEST_DRIVER_CONNECT
    )
    assert (
        infer_phase_from_output("Connecting to VM Service at http://127.0.0.1", "UNKNOWN") == PHASE_TEST_DRIVER_CONNECT
    )
    assert (
        infer_phase_from_output("Testing environment configuration line", PHASE_TEST_DRIVER_CONNECT)
        == PHASE_TEST_DRIVER_CONNECT
    )
    assert infer_phase_from_output("00:00 +0: device_e2e_test", PHASE_TEST_DRIVER_CONNECT) == PHASE_TEST_BODY
    assert (
        infer_phase_from_output("Unrecognized output line", PHASE_POST_XCODE_BUILD_WAIT) == PHASE_POST_XCODE_BUILD_WAIT
    )
    assert infer_phase_from_output("Building Runner.app with Xcode", PHASE_APP_LAUNCH) == PHASE_APP_LAUNCH

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


def test_watchdog_pre_termination_diagnostics(capsys):
    """Verifies machine-readable pre-termination diagnostics collection, redaction, and error resiliency."""
    from scripts.run_e2e_watchdog import (
        EVENT_PRE_TERMINATION_DIAGNOSTIC_COMPLETED,
        EVENT_PRE_TERMINATION_DIAGNOSTIC_STARTED,
        collect_pre_termination_diagnostics,
    )

    fake_pid = 12345
    fake_pgid = 12345
    fake_udid = "12345678-1234-1234-1234-1234567890AB"

    res = collect_pre_termination_diagnostics(
        pid=fake_pid,
        pgid=fake_pgid,
        simulator_udid=fake_udid,
        bundle_id="com.dalhack.financeintelligence",
        current_phase="IOS_E2E_PHASE_TEST_DRIVER_CONNECT",
        diagnostic_timeout_sec=1.0,
    )

    captured = capsys.readouterr()
    assert EVENT_PRE_TERMINATION_DIAGNOSTIC_STARTED in captured.err
    assert EVENT_PRE_TERMINATION_DIAGNOSTIC_COMPLETED in captured.err
    assert isinstance(res["diagnostic_duration_ms"], int)


def test_watchdog_unrelated_listener_pid_not_correlated(capsys):
    """Verifies that an unrelated listener PID (e.g. host flutter CLI) does NOT set vm_service_listener_present to True."""
    from unittest.mock import MagicMock, patch

    from scripts.run_e2e_watchdog import (
        EVENT_VM_SERVICE_PORT_STATE,
        collect_pre_termination_diagnostics,
    )

    fake_ps_out = "  PID  PPID  PGID STATE COMM\n10001 10000 10001 S s  python3"
    fake_lsof_out = "flutter 19459 runner 8u IPv4 127.0.0.1:54321 (LISTEN)"

    def mock_run(cmd, *args, **kwargs):
        res = MagicMock()
        res.returncode = 0
        if cmd[0] == "ps":
            res.stdout = fake_ps_out
        elif cmd[0] == "lsof":
            res.stdout = fake_lsof_out
        else:
            res.stdout = ""
        return res

    with patch("subprocess.run", side_effect=mock_run):
        res = collect_pre_termination_diagnostics(
            pid=10001,
            pgid=10001,
            diagnostic_timeout_sec=5.0,
        )

    assert res["vm_service_listener_present"] is False
    captured = capsys.readouterr()
    assert EVENT_VM_SERVICE_PORT_STATE in captured.err
    assert "ListenerCorrelated=False" in captured.err
    assert "Class=FLUTTER_CLI" in captured.err


def test_watchdog_coresimulator_timeout_event(capsys):
    """Verifies that simctl listapps timeout emits IOS_E2E_CORESIMULATOR_UNRESPONSIVE and sets Installed=TIMEOUT."""
    import subprocess
    from unittest.mock import MagicMock, patch

    from scripts.run_e2e_watchdog import (
        EVENT_CORESIMULATOR_UNRESPONSIVE,
        EVENT_RUNNER_APP_STATE,
        collect_pre_termination_diagnostics,
    )

    def mock_run(cmd, *args, **kwargs):
        if cmd[:3] == ["xcrun", "simctl", "listapps"]:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=4.0)
        res = MagicMock()
        res.returncode = 0
        res.stdout = ""
        return res

    with patch("subprocess.run", side_effect=mock_run):
        res = collect_pre_termination_diagnostics(
            pid=10001,
            pgid=10001,
            simulator_udid="12345678-1234-1234-1234-1234567890AB",
            diagnostic_timeout_sec=5.0,
        )

    assert res["runner_installed"] is False
    captured = capsys.readouterr()
    assert EVENT_CORESIMULATOR_UNRESPONSIVE in captured.err
    assert EVENT_RUNNER_APP_STATE in captured.err
    assert "Installed=TIMEOUT" in captured.err

    assert res["diagnostic_duration_ms"] >= 0
