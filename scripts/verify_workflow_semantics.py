#!/usr/bin/env python3
"""Workflow Semantic & Security Scanner for CI Workflows.

Enforces fail-closed rules on GitHub Actions workflow files to prevent runaway jobs,
unbounded steps, wildcard device purges, or missing explicit UDID targets.
"""

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


def verify_workflow_semantics() -> bool:
    if not WORKFLOW_PATH.exists():
        sys.stderr.write(f"CRITICAL FAIL: Workflow file '{WORKFLOW_PATH}' not found!\n")
        return False

    content = WORKFLOW_PATH.read_text(encoding="utf-8")
    lower_content = content.lower()

    # Rule 1: No wildcard purges allowed
    for pattern in PROHIBITED_WILDCARD_PATTERNS:
        if pattern in lower_content:
            sys.stderr.write(f"CRITICAL FAIL: Prohibited wildcard purge pattern '{pattern}' found in workflow!\n")
            return False

    # Rule 2: Job-level timeout-minutes must be defined on ios-build-and-simulator-e2e
    if "ios-build-and-simulator-e2e:" not in content:
        sys.stderr.write("CRITICAL FAIL: Job 'ios-build-and-simulator-e2e' missing from workflow!\n")
        return False

    ios_job_section = content.split("ios-build-and-simulator-e2e:")[1].split("final-gate-summary:")[0]
    if "timeout-minutes:" not in ios_job_section:
        sys.stderr.write("CRITICAL FAIL: Job 'ios-build-and-simulator-e2e' missing job-level 'timeout-minutes'!\n")
        return False

    # Rule 3: Check separate steps exist
    required_steps = [
        "Create Dedicated Simulator Device & Persist UDID",
        "Boot Dedicated Simulator",
        "Verify Flutter Device Visibility",
        "Run Device E2E with Process Watchdog",
        "Simulator Teardown & Cleanup",
    ]
    for req in required_steps:
        if req not in content:
            sys.stderr.write(f"CRITICAL FAIL: Required step '{req}' missing from iOS job!\n")
            return False

    # Rule 4: Check for combined unlimited boot/test step
    if "Boot Simulator & Run Device E2E Target Test" in content:
        sys.stderr.write("CRITICAL FAIL: Prohibited combined boot/test step found in workflow!\n")
        return False

    # Rule 5: Verify step timeouts and specific logic
    if "timeout-minutes: 2" not in content:
        sys.stderr.write("CRITICAL FAIL: Step timeout-minutes: 2 missing!\n")
        return False

    if "timeout-minutes: 5" not in content:
        sys.stderr.write("CRITICAL FAIL: Step timeout-minutes: 5 missing!\n")
        return False

    if "timeout-minutes: 15" not in content:
        sys.stderr.write("CRITICAL FAIL: Step timeout-minutes: 15 missing!\n")
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

    # Rule 6: Verify Watchdog Script Exists and Enforces Allowlist
    if not WATCHDOG_PATH.exists():
        sys.stderr.write(f"CRITICAL FAIL: Watchdog script '{WATCHDOG_PATH}' missing!\n")
        return False

    watchdog_content = WATCHDOG_PATH.read_text(encoding="utf-8")
    if "is_command_allowed" not in watchdog_content or "EVENT_WATCHDOG_DISALLOWED" not in watchdog_content:
        sys.stderr.write("CRITICAL FAIL: Watchdog runner script missing command allowlist enforcement!\n")
        return False

    print("WORKFLOW SEMANTIC SCANNER: 100% PASS - All fail-closed safeguards verified!")
    return True


if __name__ == "__main__":
    if not verify_workflow_semantics():
        sys.exit(1)
    sys.exit(0)
