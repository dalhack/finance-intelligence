import ast

from app.orchestration.state_machine import TERMINAL_STATES, AnalysisJobStatus


def test_state_machine_canonical_enum_invariants():
    assert AnalysisJobStatus.NEEDS_CLARIFICATION.value == "NEEDS_CLARIFICATION"
    assert AnalysisJobStatus.UNDERSTANDING_REQUEST.value == "UNDERSTANDING_REQUEST"
    assert AnalysisJobStatus.EXPIRED in TERMINAL_STATES
    assert AnalysisJobStatus.CANCELLED in TERMINAL_STATES


def test_clarification_service_ast_state_authority():
    service_path = "services/api/app/services/clarification_service.py"
    with open(service_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=service_path)

    # Inspect AST calls for validate_transition
    has_validate_transition = False
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "validate_transition"
        ):
            has_validate_transition = True

    assert has_validate_transition, "ClarificationService must use AnalysisStateMachine.validate_transition"
