#!/usr/bin/env python3
"""E2E Process Watchdog Runner for CI iOS Simulator Execution.

Spawns targeted child process in an isolated process group, streams redacted stdout/stderr
live with periodic heartbeat, enforces phase-aware tracking, fail-fast silence boundaries,
and strict fail-closed termination verification.
"""

import argparse
import os
import re
import signal
import subprocess
import sys
import time

# Event codes
EVENT_WATCHDOG_STARTED = "IOS_E2E_WATCHDOG_STARTED"
EVENT_WATCHDOG_HEARTBEAT = "IOS_E2E_WATCHDOG_HEARTBEAT"
EVENT_WATCHDOG_SUCCEEDED = "IOS_E2E_WATCHDOG_SUCCEEDED"
EVENT_WATCHDOG_CHILD_FAILED = "IOS_E2E_WATCHDOG_CHILD_FAILED"
EVENT_WATCHDOG_TIMEOUT = "IOS_E2E_TIMEOUT"
EVENT_WATCHDOG_SILENCE_TIMEOUT = "IOS_E2E_SILENCE_TIMEOUT"
EVENT_WATCHDOG_TERMINATING = "IOS_E2E_TERMINATING"
EVENT_WATCHDOG_KILLED = "IOS_E2E_KILLED"
EVENT_WATCHDOG_FAILED = "IOS_E2E_WATCHDOG_FAILED"
EVENT_WATCHDOG_DISALLOWED = "IOS_E2E_COMMAND_DISALLOWED"

# Termination Events
EVENT_SIGTERM_GROUP_SENT = "IOS_E2E_SIGTERM_GROUP_SENT"
EVENT_SIGTERM_GROUP_FAILED = "IOS_E2E_SIGTERM_GROUP_FAILED"
EVENT_SIGKILL_GROUP_SENT = "IOS_E2E_SIGKILL_GROUP_SENT"
EVENT_SIGKILL_GROUP_FAILED = "IOS_E2E_SIGKILL_GROUP_FAILED"
EVENT_PID_FALLBACK_SENT = "IOS_E2E_PID_FALLBACK_SENT"
EVENT_PID_FALLBACK_FAILED = "IOS_E2E_PID_FALLBACK_FAILED"
EVENT_PROCESS_EXIT_CONFIRMED = "IOS_E2E_PROCESS_EXIT_CONFIRMED"
EVENT_PROCESS_STILL_ALIVE = "IOS_E2E_PROCESS_STILL_ALIVE"
EVENT_PHASE_CHANGED = "IOS_E2E_PHASE_CHANGED"
EVENT_VM_SERVICE_CONNECT_TIMEOUT = "IOS_E2E_VM_SERVICE_CONNECT_TIMEOUT"

# Pre-Termination Diagnostic Event Codes
EVENT_PRE_TERMINATION_DIAGNOSTIC_STARTED = "IOS_E2E_PRE_TERMINATION_DIAGNOSTIC_STARTED"
EVENT_CHILD_PROCESS_STATE = "IOS_E2E_CHILD_PROCESS_STATE"
EVENT_RUNNER_APP_STATE = "IOS_E2E_RUNNER_APP_STATE"
EVENT_VM_SERVICE_PORT_STATE = "IOS_E2E_VM_SERVICE_PORT_STATE"
EVENT_SIMULATOR_LOG_SUMMARY = "IOS_E2E_SIMULATOR_LOG_SUMMARY"
EVENT_PRE_TERMINATION_DIAGNOSTIC_COMPLETED = "IOS_E2E_PRE_TERMINATION_DIAGNOSTIC_COMPLETED"
EVENT_PRE_TERMINATION_DIAGNOSTIC_FAILED = "IOS_E2E_PRE_TERMINATION_DIAGNOSTIC_FAILED"

# Input Validation Regexes
UDID_REGEX = re.compile(r"^[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}$", re.IGNORECASE)
BUNDLE_ID_REGEX = re.compile(r"^[a-zA-Z0-9\.\-]+$")

# Phase Constants
PHASE_DEPENDENCY_RESOLUTION = "IOS_E2E_PHASE_DEPENDENCY_RESOLUTION"
PHASE_XCODE_BUILD = "IOS_E2E_PHASE_XCODE_BUILD"
PHASE_POST_XCODE_BUILD_WAIT = "IOS_E2E_PHASE_POST_XCODE_BUILD_WAIT"
PHASE_APP_LAUNCH = "IOS_E2E_PHASE_APP_LAUNCH"
PHASE_TEST_DRIVER_CONNECT = "IOS_E2E_PHASE_TEST_DRIVER_CONNECT"
PHASE_TEST_BODY = "IOS_E2E_PHASE_TEST_BODY"
PHASE_COMPLETED = "IOS_E2E_PHASE_COMPLETED"
PHASE_UNKNOWN = "IOS_E2E_PHASE_UNKNOWN"

PHASE_RANK: dict[str, int] = {
    PHASE_UNKNOWN: 0,
    PHASE_DEPENDENCY_RESOLUTION: 1,
    PHASE_XCODE_BUILD: 2,
    PHASE_POST_XCODE_BUILD_WAIT: 3,
    PHASE_APP_LAUNCH: 4,
    PHASE_TEST_DRIVER_CONNECT: 5,
    PHASE_TEST_BODY: 6,
    PHASE_COMPLETED: 7,
}

# Redaction patterns for security
ANSI_ESCAPE_REGEX = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

REDACTION_PATTERNS = [
    (re.compile(r"(AUTHORIZATION:\s*basic\s+)[^\s\n]+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(bearer\s+)[a-zA-Z0-9\-\._~\+\/]+=*", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"([?&](?:authToken|token|auth|key|secret|password)=)[^&\s]+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(password[=:]\s*)[^\s\n&;]+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(secret[=:]\s*)[^\s\n&;]+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(token[=:]\s*)[^\s\n&;]+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"://([^:]+):([^@]+)@"), r"://\1:[REDACTED]@"),
]


def redact_line(line: str) -> str:
    """Sanitizes sensitive tokens, passwords, and authorization headers from log line."""
    cleaned = ANSI_ESCAPE_REGEX.sub("", line)
    for pattern, replacement in REDACTION_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def redact_and_truncate_line(line: str, max_length: int = 120) -> str:
    """Redacts, normalizes control characters, and bounds maximum line length for LastLine output."""
    cleaned = redact_line(line)
    normalized = re.sub(r"[\r\n\t]+", " ", cleaned).strip()
    if len(normalized) > max_length:
        return normalized[: max_length - 3] + "..."
    return normalized


def infer_phase_from_output(line: str, current_phase: str) -> str:
    """Infers current execution phase monotonically based on child stdout/stderr line."""
    lower = line.lower()
    inferred = current_phase

    if any(k in lower for k in ("pub get", "cocoapods", "running pod install")):
        inferred = PHASE_DEPENDENCY_RESOLUTION
    elif any(k in lower for k in ("xcode build done", "built build/ios/iphonesimulator")):
        inferred = PHASE_POST_XCODE_BUILD_WAIT
    elif any(k in lower for k in ("xcode build", "xcodebuild", "building runner.app")):
        inferred = PHASE_XCODE_BUILD
    elif any(k in lower for k in ("installing", "launching", "simctl install", "simctl launch")):
        inferred = PHASE_APP_LAUNCH
    elif any(
        k in lower
        for k in (
            "waiting for vm service port",
            "waiting for vm service",
            "connecting to vm service",
            "test_driver",
            "observatory",
            "flutter driver",
            "connecting to",
            "synced ",
        )
    ):
        inferred = PHASE_TEST_DRIVER_CONNECT
    elif any(
        k in lower
        for k in (
            "all tests passed",
            "test case '",
            "running test:",
            "00:00 +0:",
            "00:01 +0:",
        )
    ):
        inferred = PHASE_TEST_BODY

    # Enforce monotonic phase progression
    if PHASE_RANK.get(inferred, 0) > PHASE_RANK.get(current_phase, 0):
        return inferred
    return current_phase


def collect_pre_termination_diagnostics(
    pid: int,
    pgid: int,
    simulator_udid: str | None = None,
    bundle_id: str = "com.dalhack.financeintelligence",
    current_phase: str = PHASE_UNKNOWN,
    diagnostic_timeout_sec: float = 20.0,
) -> dict[str, str | bool | int]:
    """Collects machine-readable, redacted, and time-bounded liveness diagnostics before killing child process group."""
    start = time.time()
    effective_timeout = min(diagnostic_timeout_sec, 20.0)
    deadline = start + effective_timeout

    def remaining_cmd_timeout(max_cmd_sec: float) -> float:
        rem = deadline - time.time()
        if rem <= 0:
            raise TimeoutError("Diagnostic monotonic deadline exceeded")
        return min(max_cmd_sec, rem)

    results: dict[str, str | bool | int] = {
        "runner_installed": False,
        "runner_pid_present": False,
        "runner_alive": False,
        "runner_process_state": "UNKNOWN",
        "vm_service_listener_present": False,
        "vm_service_listener_pid": 0,
        "crash_signature_present": False,
        "diagnostic_truncated": False,
        "diagnostic_duration_ms": 0,
    }

    sys.stderr.write(
        f"[WATCHDOG DIAGNOSTIC] Event={EVENT_PRE_TERMINATION_DIAGNOSTIC_STARTED} RootPID={pid} PGID={pgid} Phase={current_phase} Timeout={effective_timeout}s\n"
    )
    sys.stderr.flush()

    try:
        # 1. Child Process Tree Inspection (COMM only, NO ARGV or ENV!)
        if sys.platform != "win32":
            try:
                ps_timeout = remaining_cmd_timeout(3.0)
                ps_res = subprocess.run(
                    ["ps", "-o", "pid,ppid,pgid,state,comm", "-g", str(pgid)],
                    capture_output=True,
                    text=True,
                    timeout=ps_timeout,
                    check=False,
                )
                if ps_res.returncode == 0:
                    lines = [l.strip() for l in ps_res.stdout.splitlines() if l.strip()][1:]
                    if len(lines) > 10:
                        results["diagnostic_truncated"] = True
                    procs_summary = "; ".join(redact_and_truncate_line(l, 80) for l in lines[:10])
                    sys.stderr.write(
                        f"[WATCHDOG DIAGNOSTIC] Event={EVENT_CHILD_PROCESS_STATE} RootPID={pid} PGID={pgid} Count={len(lines)} Procs='{procs_summary}'\n"
                    )
                    sys.stderr.flush()

                    for line in lines:
                        if "Runner" in line:
                            results["runner_pid_present"] = True
                            parts = line.split()
                            if len(parts) >= 4:
                                results["runner_process_state"] = parts[3]
                                if "Z" not in parts[3]:
                                    results["runner_alive"] = True
            except Exception as pe:  # noqa: BLE001
                sys.stderr.write(f"[WATCHDOG DIAGNOSTIC] Process tree check failed: {pe}\n")

        # 2. Simulator App Container & Status Check
        if simulator_udid and UDID_REGEX.match(simulator_udid) and sys.platform == "darwin":
            try:
                apps_timeout = remaining_cmd_timeout(4.0)
                apps_res = subprocess.run(
                    ["xcrun", "simctl", "listapps", simulator_udid],
                    capture_output=True,
                    text=True,
                    timeout=apps_timeout,
                    check=False,
                )
                if apps_res.returncode == 0 and bundle_id in apps_res.stdout:
                    results["runner_installed"] = True

                sys.stderr.write(
                    f"[WATCHDOG DIAGNOSTIC] Event={EVENT_RUNNER_APP_STATE} UDID={simulator_udid} BundleID={bundle_id} Installed={results['runner_installed']} Alive={results['runner_alive']} State={results['runner_process_state']}\n"
                )
                sys.stderr.flush()
            except Exception as ae:  # noqa: BLE001
                sys.stderr.write(f"[WATCHDOG DIAGNOSTIC] App state check failed: {ae}\n")

        # 3. VM Service Port Listener Inspection
        if sys.platform != "win32":
            try:
                lsof_timeout = remaining_cmd_timeout(3.0)
                lsof_res = subprocess.run(
                    ["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"],
                    capture_output=True,
                    text=True,
                    timeout=lsof_timeout,
                    check=False,
                )
                if lsof_res.returncode == 0:
                    for l in lsof_res.stdout.splitlines():
                        if any(k in l for k in ("Runner", "flutter", "dart")) and (
                            "127.0.0.1" in l or "localhost" in l or "*:" in l or "::1" in l
                        ):
                            results["vm_service_listener_present"] = True
                            parts = l.split()
                            if len(parts) >= 2 and parts[1].isdigit():
                                results["vm_service_listener_pid"] = int(parts[1])
                            break

                sys.stderr.write(
                    f"[WATCHDOG DIAGNOSTIC] Event={EVENT_VM_SERVICE_PORT_STATE} ListenerPresent={results['vm_service_listener_present']} ListenerPID={results['vm_service_listener_pid']}\n"
                )
                sys.stderr.flush()
            except Exception as ve:  # noqa: BLE001
                sys.stderr.write(f"[WATCHDOG DIAGNOSTIC] VM Service listener check failed: {ve}\n")

        # 4. Bounded Simulator Log Summary
        if simulator_udid and UDID_REGEX.match(simulator_udid) and sys.platform == "darwin":
            try:
                log_timeout = remaining_cmd_timeout(5.0)
                log_cmd = [
                    "xcrun",
                    "simctl",
                    "spawn",
                    simulator_udid,
                    "log",
                    "show",
                    "--predicate",
                    'process == "Runner" or message contains "VM Service" or message contains "Observatory"',
                    "--last",
                    "180s",
                    "--style",
                    "compact",
                ]
                log_res = subprocess.run(log_cmd, capture_output=True, text=True, timeout=log_timeout, check=False)
                if log_res.returncode == 0:
                    raw_lines = [l.strip() for l in log_res.stdout.splitlines() if l.strip()]
                    if len(raw_lines) > 20:
                        results["diagnostic_truncated"] = True
                    log_lines = raw_lines[-20:]
                    log_lower = "\n".join(log_lines).lower()
                    results["crash_signature_present"] = any(
                        k in log_lower for k in ("crash", "abort", "dyld", "entitlement", "exception", "terminated")
                    )
                    last_log_line = redact_and_truncate_line(log_lines[-1], 100) if log_lines else "NONE"
                    sys.stderr.write(
                        f"[WATCHDOG DIAGNOSTIC] Event={EVENT_SIMULATOR_LOG_SUMMARY} UDID={simulator_udid} CrashPresent={results['crash_signature_present']} Lines={len(log_lines)} LastLine='{last_log_line}' Truncated={results['diagnostic_truncated']}\n"
                    )
                    sys.stderr.flush()
            except Exception as le:  # noqa: BLE001
                sys.stderr.write(f"[WATCHDOG DIAGNOSTIC] Simulator log check failed: {le}\n")

    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[WATCHDOG DIAGNOSTIC] Event={EVENT_PRE_TERMINATION_DIAGNOSTIC_FAILED} Error='{e}'\n")
        sys.stderr.flush()

    duration_ms = int((time.time() - start) * 1000)
    results["diagnostic_duration_ms"] = duration_ms
    sys.stderr.write(
        f"[WATCHDOG DIAGNOSTIC] Event={EVENT_PRE_TERMINATION_DIAGNOSTIC_COMPLETED} Duration={duration_ms}ms\n"
    )
    sys.stderr.flush()

    return results


def is_command_allowed(cmd_args: list[str]) -> bool:
    """Validates command against strict CI allowlist."""
    if not cmd_args:
        return False

    # Allow flutter test/drive/devices commands
    if (
        cmd_args[0] == "flutter"
        and len(cmd_args) >= 2
        and cmd_args[1] in ("test", "drive", "devices", "emulators", "doctor")
    ):
        return True

    # Allow python verification scripts
    return bool(
        cmd_args[0] in ("python", "python3", sys.executable)
        and len(cmd_args) >= 2
        and ("scripts/" in cmd_args[1] or "tests/" in cmd_args[1] or cmd_args[1].endswith(".py") or cmd_args[1] == "-c")
    )


def terminate_process_group(
    pgid: int,
    pid: int | None = None,
    grace_period_sec: float = 5.0,
    proc: subprocess.Popen | None = None,
) -> None:
    """Terminates process group cleanly with SIGTERM/SIGKILL and verified PID fallback."""
    sys.stderr.write(
        f"[WATCHDOG SIGTERM] Event={EVENT_WATCHDOG_TERMINATING} Event={EVENT_SIGTERM_GROUP_SENT} PGID={pgid}\n"
    )
    sys.stderr.flush()

    target_pid = pid or pgid

    # 1. Send SIGTERM (try group first, fallback to direct PID)
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        sys.stderr.write(f"[WATCHDOG TERMINATION] Event={EVENT_PROCESS_EXIT_CONFIRMED} PID={target_pid}\n")
        sys.stderr.flush()
        return
    except OSError as e:
        sys.stderr.write(f"[WATCHDOG WARNING] Event={EVENT_SIGTERM_GROUP_FAILED} PGID={pgid} Error={e}\n")
        sys.stderr.flush()
        if pid:
            sys.stderr.write(f"[WATCHDOG TERMINATION] Event={EVENT_PID_FALLBACK_SENT} PID={pid} Signal=SIGTERM\n")
            sys.stderr.flush()
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                sys.stderr.write(f"[WATCHDOG TERMINATION] Event={EVENT_PROCESS_EXIT_CONFIRMED} PID={pid}\n")
                sys.stderr.flush()
                return
            except OSError:
                pass

    # 2. Wait for process exit during grace period
    start_time = time.time()
    while time.time() - start_time < grace_period_sec:
        if proc and proc.poll() is not None:
            sys.stderr.write(f"[WATCHDOG TERMINATION] Event={EVENT_PROCESS_EXIT_CONFIRMED} PID={target_pid}\n")
            sys.stderr.flush()
            return

        try:
            res_pid, _ = os.waitpid(target_pid, os.WNOHANG)
            if res_pid > 0:
                sys.stderr.write(f"[WATCHDOG TERMINATION] Event={EVENT_PROCESS_EXIT_CONFIRMED} PID={target_pid}\n")
                sys.stderr.flush()
                return
        except OSError:
            pass

        try:
            os.kill(target_pid, 0)
        except (ProcessLookupError, OSError):
            sys.stderr.write(f"[WATCHDOG TERMINATION] Event={EVENT_PROCESS_EXIT_CONFIRMED} PID={target_pid}\n")
            sys.stderr.flush()
            return

        time.sleep(0.05)

    # 3. Escalation: Send SIGKILL (try group first, fallback to direct PID)
    sys.stderr.write(f"[WATCHDOG SIGKILL] Event={EVENT_WATCHDOG_KILLED} Event={EVENT_SIGKILL_GROUP_SENT} PGID={pgid}\n")
    sys.stderr.flush()

    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        sys.stderr.write(f"[WATCHDOG TERMINATION] Event={EVENT_PROCESS_EXIT_CONFIRMED} PID={target_pid}\n")
        sys.stderr.flush()
        return
    except OSError as e:
        sys.stderr.write(f"[WATCHDOG WARNING] Event={EVENT_SIGKILL_GROUP_FAILED} PGID={pgid} Error={e}\n")
        sys.stderr.flush()
        if pid:
            sys.stderr.write(f"[WATCHDOG TERMINATION] Event={EVENT_PID_FALLBACK_SENT} PID={pid} Signal=SIGKILL\n")
            sys.stderr.flush()
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                sys.stderr.write(f"[WATCHDOG TERMINATION] Event={EVENT_PROCESS_EXIT_CONFIRMED} PID={pid}\n")
                sys.stderr.flush()
                return
            except OSError as kill_err:
                sys.stderr.write(
                    f"CRITICAL FAIL-CLOSED [{EVENT_PID_FALLBACK_FAILED}]: Could not terminate PID {pid}: {kill_err}\n"
                )
                sys.stderr.flush()

    # 4. Final verification loop post SIGKILL
    start_verify = time.time()
    while time.time() - start_verify < 2.0:
        if proc and proc.poll() is not None:
            sys.stderr.write(f"[WATCHDOG TERMINATION] Event={EVENT_PROCESS_EXIT_CONFIRMED} PID={target_pid}\n")
            sys.stderr.flush()
            return

        try:
            res_pid, _ = os.waitpid(target_pid, os.WNOHANG)
            if res_pid > 0:
                sys.stderr.write(f"[WATCHDOG TERMINATION] Event={EVENT_PROCESS_EXIT_CONFIRMED} PID={target_pid}\n")
                sys.stderr.flush()
                return
        except OSError:
            pass

        try:
            os.kill(target_pid, 0)
            time.sleep(0.05)
        except (ProcessLookupError, OSError):
            sys.stderr.write(f"[WATCHDOG TERMINATION] Event={EVENT_PROCESS_EXIT_CONFIRMED} PID={target_pid}\n")
            sys.stderr.flush()
            return

    sys.stderr.write(
        f"CRITICAL FAIL-CLOSED [{EVENT_PROCESS_STILL_ALIVE}]: Process PID {target_pid} still alive after SIGKILL!\n"
    )
    sys.stderr.flush()
    raise RuntimeError(
        f"CRITICAL FAIL-CLOSED [{EVENT_PROCESS_STILL_ALIVE}]: Could not terminate process PID {target_pid}"
    )


def run_watchdog(
    cmd_args: list[str],
    timeout_seconds: int = 900,
    silence_timeout_seconds: int = 180,
    heartbeat_interval_seconds: int = 30,
    grace_seconds: float = 5.0,
    cwd: str | None = None,
    env: dict | None = None,
    simulator_udid: str | None = None,
    bundle_id: str = "com.dalhack.financeintelligence",
) -> int:
    """Runs command in isolated process group with live log redaction, phase tracking, and silence watchdog."""
    if timeout_seconds <= 0:
        raise ValueError(f"Invalid timeout_seconds {timeout_seconds}; must be > 0")
    if silence_timeout_seconds <= 0:
        raise ValueError(f"Invalid silence_timeout_seconds {silence_timeout_seconds}; must be > 0")
    if grace_seconds < 0.1:
        raise ValueError(f"Invalid grace_seconds {grace_seconds}; must be >= 0.1")

    if not is_command_allowed(cmd_args):
        sys.stderr.write(f"CRITICAL: {EVENT_WATCHDOG_DISALLOWED}: Command {cmd_args} is not in CI allowlist!\n")
        return 126

    start_time = time.time()
    last_child_output_time = start_time
    last_heartbeat_time = start_time
    current_phase = PHASE_UNKNOWN
    last_child_output_line = ""

    # Spawn process in its own process group
    proc = subprocess.Popen(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=cwd,
        env=env or os.environ.copy(),
        start_new_session=True,
    )

    pgid = os.getpgid(proc.pid)
    sys.stdout.write(
        f"[WATCHDOG START] Event={EVENT_WATCHDOG_STARTED} PID={proc.pid} PGID={pgid} Timeout={timeout_seconds}s SilenceTimeout={silence_timeout_seconds}s Grace={grace_seconds}s Phase={current_phase}\n"
    )
    sys.stdout.flush()

    assert proc.stdout is not None, "proc.stdout cannot be None when stdout=PIPE"
    os.set_blocking(proc.stdout.fileno(), False)

    try:
        while True:
            now = time.time()
            elapsed = now - start_time
            child_silence = now - last_child_output_time

            # Check overall hard timeout limit
            if elapsed >= timeout_seconds:
                sys.stderr.write(
                    f"\nCRITICAL FAIL-CLOSED [{EVENT_WATCHDOG_TIMEOUT}]: Execution exceeded {timeout_seconds}s timeout boundary! Phase={current_phase} Elapsed={int(elapsed)}s PID={proc.pid} PGID={pgid}\n"
                )
                sys.stderr.flush()
                collect_pre_termination_diagnostics(
                    pid=proc.pid,
                    pgid=pgid,
                    simulator_udid=simulator_udid,
                    bundle_id=bundle_id,
                    current_phase=current_phase,
                )
                terminate_process_group(pgid, pid=proc.pid, grace_period_sec=grace_seconds, proc=proc)
                return 124

            # Check child process silence timeout boundary
            if child_silence >= silence_timeout_seconds:
                sys.stderr.write(
                    f"\nCRITICAL FAIL-CLOSED [{EVENT_WATCHDOG_SILENCE_TIMEOUT}]: Child process produced no output for {int(child_silence)}s (boundary {silence_timeout_seconds}s exceeded)! Phase={current_phase} Elapsed={int(elapsed)}s PID={proc.pid} PGID={pgid} LastChildOutput='{last_child_output_line}'\n"
                )
                sys.stderr.flush()
                collect_pre_termination_diagnostics(
                    pid=proc.pid,
                    pgid=pgid,
                    simulator_udid=simulator_udid,
                    bundle_id=bundle_id,
                    current_phase=current_phase,
                )
                terminate_process_group(pgid, pid=proc.pid, grace_period_sec=grace_seconds, proc=proc)
                return 1

            # Read available output lines
            try:
                line = proc.stdout.readline()
                if line:
                    sanitized_line = redact_line(line)
                    sys.stdout.write(sanitized_line)
                    sys.stdout.flush()

                    # Update phase tracking & silence timestamp for REAL child output line
                    last_child_output_time = now
                    last_child_output_line = sanitized_line.strip()
                    new_phase = infer_phase_from_output(line, current_phase)
                    if new_phase != current_phase:
                        current_phase = new_phase
                        sys.stdout.write(
                            f"[WATCHDOG PHASE] Event={EVENT_PHASE_CHANGED} Phase={current_phase} Elapsed={int(elapsed)}s\n"
                        )
                        sys.stdout.flush()
                else:
                    # Check if process exited
                    poll_res = proc.poll()
                    if poll_res is not None:
                        # Flush any remaining output
                        remaining = proc.stdout.read()
                        if remaining:
                            sys.stdout.write(redact_line(remaining))
                            sys.stdout.flush()

                        if poll_res == 0:
                            current_phase = PHASE_COMPLETED
                            sys.stdout.write(
                                f"[WATCHDOG SUCCESS] Event={EVENT_WATCHDOG_SUCCEEDED} PID={proc.pid} ExitCode=0 Phase={current_phase}\n"
                            )
                        else:
                            sys.stderr.write(
                                f"[WATCHDOG CHILD FAIL] Event={EVENT_WATCHDOG_CHILD_FAILED} PID={proc.pid} ExitCode={poll_res} Phase={current_phase}\n"
                            )
                        sys.stdout.flush()
                        sys.stderr.flush()
                        return poll_res
                    time.sleep(0.05)
            except Exception:  # noqa: BLE001
                time.sleep(0.05)

            # Periodic heartbeat check (HEARTBEAT DOES NOT RESET last_child_output_time!)
            if now - last_heartbeat_time >= heartbeat_interval_seconds:
                silence_duration = int(now - last_child_output_time)
                redacted_last_line = (
                    redact_and_truncate_line(last_child_output_line, max_length=120)
                    if last_child_output_line
                    else "NONE"
                )
                sys.stdout.write(
                    f"[WATCHDOG HEARTBEAT] Event={EVENT_WATCHDOG_HEARTBEAT} Elapsed={int(elapsed)}s Silence={silence_duration}s Phase={current_phase} LastLine='{redacted_last_line}' Status=RUNNING PGID={pgid}\n"
                )
                sys.stdout.flush()
                last_heartbeat_time = now

    except KeyboardInterrupt:
        sys.stderr.write(f"\n[WATCHDOG INTERRUPT] Received SIGINT/KeyboardInterrupt. Terminating PGID {pgid}...\n")
        terminate_process_group(pgid, pid=proc.pid, grace_period_sec=grace_seconds, proc=proc)
        return 130
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(
            f"\n[WATCHDOG ERROR] Event={EVENT_WATCHDOG_FAILED}: Unexpected exception: {e}. Terminating PGID {pgid}...\n"
        )
        terminate_process_group(pgid, pid=proc.pid, grace_period_sec=grace_seconds, proc=proc)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E Process Watchdog Runner")
    parser.add_argument("--timeout-seconds", type=int, default=900, help="Max execution timeout in seconds")
    parser.add_argument("--silence-timeout-seconds", type=int, default=180, help="Max child output silence in seconds")
    parser.add_argument("--heartbeat-seconds", type=int, default=30, help="Heartbeat logging interval")
    parser.add_argument("--grace-seconds", type=float, default=5.0, help="Grace period for SIGTERM before SIGKILL")
    parser.add_argument("--cwd", type=str, default=None, help="Working directory for child command")
    parser.add_argument("--simulator-udid", type=str, default=None, help="Target iOS Simulator UDID for diagnostics")
    parser.add_argument(
        "--bundle-id",
        type=str,
        default="com.dalhack.financeintelligence",
        help="Target iOS App Bundle Identifier",
    )
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Target command to execute")

    args = parser.parse_args()

    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    code = run_watchdog(
        cmd_args=cmd,
        timeout_seconds=args.timeout_seconds,
        silence_timeout_seconds=args.silence_timeout_seconds,
        heartbeat_interval_seconds=args.heartbeat_seconds,
        grace_seconds=args.grace_seconds,
        cwd=args.cwd,
        simulator_udid=args.simulator_udid,
        bundle_id=args.bundle_id,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
