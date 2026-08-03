#!/usr/bin/env python3
"""Workflow Semantic & Timeout Budget Scanner for CI Workflows.

Enforces machine-readable timeout budget invariants, fail-closed step boundaries,
dangling process tree safeguards, and explicit UDID simulator ownership checks.
"""

import re
import sys
from pathlib import Path

WORKFLOW_PATH = Path(".github/workflows/ci.yml")
WATCHDOG_PATH = Path("scripts/run_e2e_watchdog.py")

PROHIBITED_WILDCARD_PATTERNS = [
    "shutdown all",
    "delete all",
    "simctl shutdown all",
    "simctl delete all",
    "simctl erase all",
]

# Minimum Budget Reserve Constants (minutes)
MIN_SETUP_BUILD_RESERVE = 8
MIN_SAFETY_MARGIN = 3
MIN_CLEANUP_RESERVE = 3
MIN_E2E_WATCHDOG_TIMEOUT = 15


def parse_job_timeout(job_section: str) -> int:
    """Parses job-level timeout-minutes as integer."""
    match = re.search(r"timeout-minutes:\s*(\d+)", job_section)
    if not match:
        raise ValueError("Missing job-level 'timeout-minutes'")
    return int(match.group(1))


def parse_step_timeouts(job_section: str) -> dict[str, int]:
    """Parses step-level timeouts for key iOS steps."""
    step_timeouts = {}
    steps = job_section.split("- name:")
    for step in steps[1:]:
        name_line = step.splitlines()[0].strip()
        match = re.search(r"timeout-minutes:\s*(\d+)", step)
        if match:
            timeout_val = int(match.group(1))
            if "Create Dedicated Simulator" in name_line:
                step_timeouts["create"] = timeout_val
            elif "Boot Dedicated Simulator" in name_line:
                step_timeouts["boot"] = timeout_val
            elif "Verify Flutter Device Visibility" in name_line:
                step_timeouts["visibility"] = timeout_val
            elif "Run Device E2E" in name_line:
                step_timeouts["e2e"] = timeout_val
            elif "Collect Redacted Diagnostic Context" in name_line:
                step_timeouts["diagnostic"] = timeout_val
            elif "Simulator Teardown & Cleanup" in name_line:
                step_timeouts["cleanup"] = timeout_val
    return step_timeouts


def verify_workflow_semantics(workflow_content: str | None = None) -> bool:
    """Enforces strict timeout budget model and security invariants on workflow YAML content."""
    content = workflow_content if workflow_content is not None else WORKFLOW_PATH.read_text(encoding="utf-8")
    lower_content = content.lower()

    # Rule 1: No wildcard purges allowed
    for pattern in PROHIBITED_WILDCARD_PATTERNS:
        if pattern in lower_content:
            sys.stderr.write(f"CRITICAL FAIL: Prohibited wildcard purge pattern '{pattern}' found in workflow!\n")
            return False

    # Rule 2: Verify job presence and extract job section
    if "ios-build-and-simulator-e2e:" not in content:
        sys.stderr.write("CRITICAL FAIL: Job 'ios-build-and-simulator-e2e' missing from workflow!\n")
        return False

    ios_job_section = content.split("ios-build-and-simulator-e2e:")[1].split("final-gate-summary:")[0]

    # Rule 3: Parse job-level timeout
    try:
        job_timeout = parse_job_timeout(ios_job_section)
    except ValueError as e:
        sys.stderr.write(f"CRITICAL FAIL: {e}\n")
        return False

    # Rule 4: Parse step-level timeouts
    step_timeouts = parse_step_timeouts(ios_job_section)
    required_steps = ["create", "boot", "visibility", "e2e", "diagnostic", "cleanup"]
    for req in required_steps:
        if req not in step_timeouts:
            sys.stderr.write(f"CRITICAL FAIL: Step timeout for '{req}' missing from iOS job!\n")
            return False

    create_t = step_timeouts["create"]
    boot_t = step_timeouts["boot"]
    visibility_t = step_timeouts["visibility"]
    e2e_t = step_timeouts["e2e"]
    diagnostic_t = step_timeouts["diagnostic"]
    cleanup_t = step_timeouts["cleanup"]

    # Rule 5: Step Timeout Boundary Checks
    if cleanup_t < MIN_CLEANUP_RESERVE:
        sys.stderr.write(
            f"CRITICAL FAIL: Cleanup timeout {cleanup_t}m is below minimum reserve of {MIN_CLEANUP_RESERVE}m!\n"
        )
        return False

    if e2e_t < MIN_E2E_WATCHDOG_TIMEOUT:
        sys.stderr.write(
            f"CRITICAL FAIL: E2E timeout {e2e_t}m is below required minimum of {MIN_E2E_WATCHDOG_TIMEOUT}m!\n"
        )
        return False

    for name, st in step_timeouts.items():
        if st >= job_timeout:
            sys.stderr.write(
                f"CRITICAL FAIL: Step '{name}' timeout ({st}m) is >= job-level timeout ({job_timeout}m)!\n"
            )
            return False

    # Rule 6: Machine-Readable Timeout Budget Model Invariant
    # JOB_TIMEOUT >= setup_build_reserve + sum(step_timeouts) + safety_margin
    sum_step_timeouts = create_t + boot_t + visibility_t + e2e_t + diagnostic_t + cleanup_t
    required_min_job_budget = sum_step_timeouts + MIN_SETUP_BUILD_RESERVE + MIN_SAFETY_MARGIN

    if job_timeout < required_min_job_budget:
        sys.stderr.write(
            f"CRITICAL FAIL: Job timeout {job_timeout}m is insufficient! "
            f"Sum of step timeouts ({sum_step_timeouts}m) + Setup/Build reserve ({MIN_SETUP_BUILD_RESERVE}m) + "
            f"Safety margin ({MIN_SAFETY_MARGIN}m) requires at least {required_min_job_budget}m!\n"
        )
        return False

    # Rule 7: Cleanup Headroom Guarantee
    # Remaining job headroom after maximum step execution prior to cleanup MUST be >= cleanup_t
    max_execution_prior_to_cleanup = MIN_SETUP_BUILD_RESERVE + create_t + boot_t + visibility_t + e2e_t + diagnostic_t
    remaining_headroom_for_cleanup = job_timeout - max_execution_prior_to_cleanup

    if remaining_headroom_for_cleanup < cleanup_t:
        sys.stderr.write(
            f"CRITICAL FAIL: Insufficient headroom for cleanup! "
            f"Job headroom before cleanup is {remaining_headroom_for_cleanup}m, but cleanup requires {cleanup_t}m!\n"
        )
        return False

    # Rule 8: Required logic assertions
    if "Boot Simulator & Run Device E2E Target Test" in content:
        sys.stderr.write("CRITICAL FAIL: Prohibited combined boot/test step found in workflow!\n")
        return False

    if "python ../../scripts/run_e2e_watchdog.py" not in content:
        sys.stderr.write("CRITICAL FAIL: E2E step must run via run_e2e_watchdog.py!\n")
        return False

    if '-d "$SIMULATOR_UDID"' not in content:
        sys.stderr.write("CRITICAL FAIL: E2E step must specify '-d \"$SIMULATOR_UDID\"'!\n")
        return False

    if "if: always()" not in content:
        sys.stderr.write("CRITICAL FAIL: Cleanup step must specify 'if: always()'!\n")
        return False

    # Rule 9: Verify Watchdog Script Exists and Enforces Allowlist
    if workflow_content is None and not WATCHDOG_PATH.exists():
        sys.stderr.write(f"CRITICAL FAIL: Watchdog script '{WATCHDOG_PATH}' missing!\n")
        return False

    if WATCHDOG_PATH.exists():
        watchdog_content = WATCHDOG_PATH.read_text(encoding="utf-8")
        if "is_command_allowed" not in watchdog_content or "EVENT_WATCHDOG_DISALLOWED" not in watchdog_content:
            sys.stderr.write("CRITICAL FAIL: Watchdog runner script missing command allowlist enforcement!\n")
            return False

    if workflow_content is None:
        print(
            f"WORKFLOW TIMEOUT BUDGET SCANNER: 100% PASS - Job Timeout={job_timeout}m >= Required={required_min_job_budget}m!"
        )
    return True


if __name__ == "__main__":
    if not verify_workflow_semantics():
        sys.exit(1)
    sys.exit(0)
