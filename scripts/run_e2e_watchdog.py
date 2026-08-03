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
EVENT_WATCHDOG_SUCCESS = "IOS_E2E_WATCHDOG_SUCCESS"
EVENT_WATCHDOG_FAILURE = "IOS_E2E_WATCHDOG_FAILURE"
EVENT_WATCHDOG_TIMEOUT = "IOS_E2E_TIMEOUT"
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
    """Terminates entire process group cleanly with SIGTERM, falling back to SIGKILL."""
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError as e:
        sys.stderr.write(f"[WATCHDOG WARNING] SIGTERM error for pgid {pgid}: {e}\n")

    start_time = time.time()
    while time.time() - start_time < grace_period_sec:
        try:
            # Check if process group is still alive
            os.killpg(pgid, 0)
            time.sleep(0.2)
        except ProcessLookupError:
            return
        except OSError:
            break

    try:
        sys.stderr.write(f"[WATCHDOG] Sending SIGKILL to process group {pgid}\n")
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError as e:
        sys.stderr.write(f"[WATCHDOG WARNING] SIGKILL error for pgid {pgid}: {e}\n")


def run_watchdog(
    cmd_args: list[str],
    timeout_seconds: int = 900,
    heartbeat_interval_seconds: int = 30,
    cwd: str | None = None,
    env: dict | None = None,
) -> int:
    """Runs command in isolated process group with live log redaction and timeout watchdog."""
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
        f"[WATCHDOG START] Event={EVENT_WATCHDOG_SUCCESS} PID={proc.pid} PGID={pgid} Timeout={timeout_seconds}s\n"
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
                terminate_process_group(pgid)
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
                        return poll_res
                    time.sleep(0.1)
            except Exception:  # noqa: BLE001
                time.sleep(0.1)

            # Periodic heartbeat check
            if now - last_heartbeat_time >= heartbeat_interval_seconds:
                silence_duration = int(now - last_activity_time)
                sys.stdout.write(
                    f"[WATCHDOG HEARTBEAT] Elapsed={int(elapsed)}s Silence={silence_duration}s Status=RUNNING PGID={pgid}\n"
                )
                sys.stdout.flush()
                last_heartbeat_time = now

    except KeyboardInterrupt:
        sys.stderr.write(f"\n[WATCHDOG INTERRUPT] Received SIGINT/KeyboardInterrupt. Terminating PGID {pgid}...\n")
        terminate_process_group(pgid)
        return 130
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"\n[WATCHDOG ERROR] Unexpected exception: {e}. Terminating PGID {pgid}...\n")
        terminate_process_group(pgid)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E Process Watchdog Runner")
    parser.add_argument("--timeout-seconds", type=int, default=900, help="Max execution timeout in seconds")
    parser.add_argument("--heartbeat-seconds", type=int, default=30, help="Heartbeat logging interval")
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
        cwd=args.cwd,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
