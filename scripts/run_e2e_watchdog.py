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

# Phase Constants
PHASE_DEPENDENCY_RESOLUTION = "IOS_E2E_PHASE_DEPENDENCY_RESOLUTION"
PHASE_XCODE_BUILD = "IOS_E2E_PHASE_XCODE_BUILD"
PHASE_POST_XCODE_BUILD_WAIT = "IOS_E2E_PHASE_POST_XCODE_BUILD_WAIT"
PHASE_APP_LAUNCH = "IOS_E2E_PHASE_APP_LAUNCH"
PHASE_TEST_DRIVER_CONNECT = "IOS_E2E_PHASE_TEST_DRIVER_CONNECT"
PHASE_TEST_BODY = "IOS_E2E_PHASE_TEST_BODY"
PHASE_COMPLETED = "IOS_E2E_PHASE_COMPLETED"
PHASE_UNKNOWN = "IOS_E2E_PHASE_UNKNOWN"

# Redaction patterns for security
REDACTION_PATTERNS = [
    (re.compile(r"(AUTHORIZATION:\s*basic\s+)[^\s\n]+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(bearer\s+)[a-zA-Z0-9\-\._~\+\/]+=*", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(password[=:]\s*)[^\s\n&;]+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(secret[=:]\s*)[^\s\n&;]+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(token[=:]\s*)[^\s\n&;]+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"://([^:]+):([^@]+)@"), r"://\1:[REDACTED]@"),
]


def redact_line(line: str) -> str:
    """Sanitizes sensitive tokens, passwords, and authorization headers from log line."""
    cleaned = line
    for pattern, replacement in REDACTION_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def infer_phase_from_output(line: str, current_phase: str) -> str:
    """Infers current execution phase based on child stdout/stderr line."""
    lower = line.lower()
    if any(k in lower for k in ("pub get", "cocoapods", "running pod install")):
        return PHASE_DEPENDENCY_RESOLUTION
    if any(k in lower for k in ("xcode build done", "built build/ios/iphonesimulator")):
        return PHASE_POST_XCODE_BUILD_WAIT
    if any(k in lower for k in ("xcode build", "xcodebuild", "building runner.app")):
        return PHASE_XCODE_BUILD
    if any(k in lower for k in ("installing", "launching", "simctl install", "simctl launch")):
        return PHASE_APP_LAUNCH
    if any(
        k in lower
        for k in (
            "connecting to vm service",
            "test_driver",
            "observatory",
            "flutter driver",
            "connecting to",
            "synced ",
        )
    ):
        return PHASE_TEST_DRIVER_CONNECT
    if any(k in lower for k in ("all tests passed", "test case", "assertion", "running test", "00:")):
        return PHASE_TEST_BODY
    return current_phase


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
                terminate_process_group(pgid, pid=proc.pid, grace_period_sec=grace_seconds, proc=proc)
                return 124

            # Check child process silence timeout boundary
            if child_silence >= silence_timeout_seconds:
                sys.stderr.write(
                    f"\nCRITICAL FAIL-CLOSED [{EVENT_WATCHDOG_SILENCE_TIMEOUT}]: Child process produced no output for {int(child_silence)}s (boundary {silence_timeout_seconds}s exceeded)! Phase={current_phase} Elapsed={int(elapsed)}s PID={proc.pid} PGID={pgid} LastChildOutput='{last_child_output_line}'\n"
                )
                sys.stderr.flush()
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
                sys.stdout.write(
                    f"[WATCHDOG HEARTBEAT] Event={EVENT_WATCHDOG_HEARTBEAT} Elapsed={int(elapsed)}s Silence={silence_duration}s Phase={current_phase} Status=RUNNING PGID={pgid}\n"
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
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
