"""Unit tests for Workflow Semantic Scanner (scripts/verify_workflow_semantics.py)."""

from scripts.verify_workflow_semantics import PROHIBITED_WILDCARD_PATTERNS, verify_workflow_semantics


def test_workflow_semantic_scanner_current_pass():
    """Verifies workflow semantic scanner passes on current codebase."""
    res = verify_workflow_semantics()
    assert res is True, "Workflow semantic scanner should pass on valid workflow"


def test_prohibited_wildcard_patterns():
    """Verifies prohibited wildcard patterns list is non-empty."""
    assert len(PROHIBITED_WILDCARD_PATTERNS) >= 4
    assert "simctl delete all" in PROHIBITED_WILDCARD_PATTERNS
    assert "simctl shutdown all" in PROHIBITED_WILDCARD_PATTERNS
