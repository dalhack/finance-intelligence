"""Unit tests and negative fixture verification for Workflow Semantic & Timeout Budget Scanner."""

from pathlib import Path

from scripts.verify_workflow_semantics import (
    PROHIBITED_WILDCARD_PATTERNS,
    verify_workflow_semantics,
)

WORKFLOW_PATH = Path(".github/workflows/ci.yml")


def test_workflow_semantic_scanner_current_pass():
    """Verifies workflow semantic scanner passes on current ci.yml with 40m job budget."""
    res = verify_workflow_semantics()
    assert res is True, "Workflow semantic scanner should pass on valid workflow"


def test_prohibited_wildcard_patterns():
    """Verifies prohibited wildcard patterns list is non-empty."""
    assert len(PROHIBITED_WILDCARD_PATTERNS) >= 4
    assert "simctl delete all" in PROHIBITED_WILDCARD_PATTERNS
    assert "simctl shutdown all" in PROHIBITED_WILDCARD_PATTERNS


def test_negative_timeout_budget_fixtures():
    """Self-test scanner against defective workflow timeout budget fixtures."""
    valid_content = WORKFLOW_PATH.read_text(encoding="utf-8")

    # Negative Fixture 1: Insufficient job timeout (25m < required 40m)
    bad_fixture_1 = valid_content.replace("timeout-minutes: 40", "timeout-minutes: 25")
    assert verify_workflow_semantics(bad_fixture_1) is False

    # Negative Fixture 2: Step timeout >= job timeout
    bad_fixture_2 = valid_content.replace(
        "Run Device E2E with Process Watchdog\n        working-directory: apps/mobile\n        timeout-minutes: 15",
        "Run Device E2E with Process Watchdog\n        working-directory: apps/mobile\n        timeout-minutes: 40",
    )
    assert verify_workflow_semantics(bad_fixture_2) is False

    # Negative Fixture 3: Cleanup timeout below 3m reserve
    bad_fixture_3 = valid_content.replace(
        "Simulator Teardown & Cleanup\n        if: always()\n        timeout-minutes: 3",
        "Simulator Teardown & Cleanup\n        if: always()\n        timeout-minutes: 1",
    )
    assert verify_workflow_semantics(bad_fixture_3) is False

    # Negative Fixture 4: Wildcard purge pattern
    bad_fixture_4 = valid_content.replace("xcrun simctl delete", "xcrun simctl delete all")
    assert verify_workflow_semantics(bad_fixture_4) is False

    # Negative Fixture 5: Cleanup not if: always()
    bad_fixture_5 = valid_content.replace("if: always()", "if: success()")
    assert verify_workflow_semantics(bad_fixture_5) is False

    # Negative Fixture 6: Invalid --device-timeout flag on flutter test
    bad_fixture_6 = valid_content.replace(
        '-d "$SIMULATOR_UDID"',
        '-d "$SIMULATOR_UDID" --device-timeout=30',
    )
    assert verify_workflow_semantics(bad_fixture_6) is False
