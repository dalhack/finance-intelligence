#!/usr/bin/env python3
"""E2E Process Watchdog Runner for CI iOS Simulator Execution.

Spawns targeted child process in an isolated process group, streams redacted stdout/stderr
live with periodic heartbeat, and enforces strict fail-closed termination on timeout.
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
EVENT_WATCHDOG_TERMINATING = "IOS_E2E_TERMINATING"
EVENT_WATCHDOG_KILLED = "IOS_E2E_KILLED"
EVENT_WATCHDOG_FAILED = "IOS_E2E_WATCHDOG_FAILED"
EVENT_WATCHDOG_DISALLOWED = "IOS_E2E_COMMAND_DISALLOWED"

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


def terminate_process_group(pgid: int, grace_period_sec: float = 5.0) -> None:
    """Terminates entire process group cleanly with SIGTERM, falling back to SIGKILL and direct PID kill."""
    sys.stderr.write(f"[WATCHDOG SIGTERM] Event={EVENT_WATCHDOG_TERMINATING} PGID={pgid}\n")
    sys.stderr.flush()

    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError as e:
        sys.stderr.write(f"[WATCHDOG WARNING] SIGTERM error for pgid {pgid}: {e}\n")
        try:
            os.kill(pgid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass

    start_time = time.time()
    while time.time() - start_time < grace_period_sec:
        try:
            os.killpg(pgid, 0)
            time.sleep(0.05)
        except ProcessLookupError:
            return
        except OSError:
            try:
                os.kill(pgid, 0)
                time.sleep(0.05)
            except (ProcessLookupError, OSError):
                return

    try:
        sys.stderr.write(f"[WATCHDOG SIGKILL] Event={EVENT_WATCHDOG_KILLED} PGID={pgid}\n")
        sys.stderr.flush()
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError as e:
        sys.stderr.write(f"[WATCHDOG WARNING] SIGKILL error for pgid {pgid}: {e}\n")
        try:
            os.kill(pgid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except OSError as kill_err:
            sys.stderr.write(
                f"CRITICAL FAIL-CLOSED [KILL_FAILED]: Could not terminate process group or PID {pgid}: {kill_err}\n"
            )
            raise RuntimeError(f"KILL_FAILED: Could not terminate process group or PID {pgid}") from kill_err


def run_watchdog(
    cmd_args: list[str],
    timeout_seconds: int = 900,
    heartbeat_interval_seconds: int = 30,
    grace_seconds: float = 5.0,
    cwd: str | None = None,
    env: dict | None = None,
) -> int:
    """Runs command in isolated process group with live log redaction and timeout watchdog."""
    if timeout_seconds <= 0:
        raise ValueError(f"Invalid timeout_seconds {timeout_seconds}; must be > 0")
    if grace_seconds < 0.1:
        raise ValueError(f"Invalid grace_seconds {grace_seconds}; must be >= 0.1")

    if not is_command_allowed(cmd_args):
        sys.stderr.write(f"CRITICAL: {EVENT_WATCHDOG_DISALLOWED}: Command {cmd_args} is not in CI allowlist!\n")
        return 126

    start_time = time.time()
    last_activity_time = start_time
    last_heartbeat_time = start_time

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
        f"[WATCHDOG START] Event={EVENT_WATCHDOG_STARTED} PID={proc.pid} PGID={pgid} Timeout={timeout_seconds}s Grace={grace_seconds}s\n"
    )
    sys.stdout.flush()

    assert proc.stdout is not None, "proc.stdout cannot be None when stdout=PIPE"
    # Non-blocking stdout reading mechanism
    os.set_blocking(proc.stdout.fileno(), False)

    try:
        while True:
            now = time.time()
            elapsed = now - start_time

            # Check overall timeout limit
            if elapsed >= timeout_seconds:
                sys.stderr.write(
                    f"\nCRITICAL FAIL-CLOSED [{EVENT_WATCHDOG_TIMEOUT}]: Execution exceeded {timeout_seconds}s timeout boundary!\n"
                )
                sys.stderr.flush()
                terminate_process_group(pgid, grace_period_sec=grace_seconds)
                return 124

            # Read available output lines
            try:
                line = proc.stdout.readline()
                if line:
                    sanitized_line = redact_line(line)
                    sys.stdout.write(sanitized_line)
                    sys.stdout.flush()
                    last_activity_time = now
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
                            sys.stdout.write(
                                f"[WATCHDOG SUCCESS] Event={EVENT_WATCHDOG_SUCCEEDED} PID={proc.pid} ExitCode=0\n"
                            )
                        else:
                            sys.stderr.write(
                                f"[WATCHDOG CHILD FAIL] Event={EVENT_WATCHDOG_CHILD_FAILED} PID={proc.pid} ExitCode={poll_res}\n"
                            )
                        sys.stdout.flush()
                        sys.stderr.flush()
                        return poll_res
                    time.sleep(0.05)
            except Exception:  # noqa: BLE001
                time.sleep(0.05)

            # Periodic heartbeat check
            if now - last_heartbeat_time >= heartbeat_interval_seconds:
                silence_duration = int(now - last_activity_time)
                sys.stdout.write(
                    f"[WATCHDOG HEARTBEAT] Event={EVENT_WATCHDOG_HEARTBEAT} Elapsed={int(elapsed)}s Silence={silence_duration}s Status=RUNNING PGID={pgid}\n"
                )
                sys.stdout.flush()
                last_heartbeat_time = now

    except KeyboardInterrupt:
        sys.stderr.write(f"\n[WATCHDOG INTERRUPT] Received SIGINT/KeyboardInterrupt. Terminating PGID {pgid}...\n")
        terminate_process_group(pgid, grace_period_sec=grace_seconds)
        return 130
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(
            f"\n[WATCHDOG ERROR] Event={EVENT_WATCHDOG_FAILED}: Unexpected exception: {e}. Terminating PGID {pgid}...\n"
        )
        terminate_process_group(pgid, grace_period_sec=grace_seconds)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E Process Watchdog Runner")
    parser.add_argument("--timeout-seconds", type=int, default=900, help="Max execution timeout in seconds")
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
        heartbeat_interval_seconds=args.heartbeat_seconds,
        grace_seconds=args.grace_seconds,
        cwd=args.cwd,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
