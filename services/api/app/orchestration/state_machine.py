from enum import Enum

from services.api.app.orchestration.exceptions import OrchestrationException


class AnalysisJobStatus(str, Enum):
    RECEIVED = "RECEIVED"
    UNDERSTANDING_REQUEST = "UNDERSTANDING_REQUEST"
    PLANNING = "PLANNING"
    POLICY_CHECK = "POLICY_CHECK"
    RETRIEVING_INTERNAL_SOURCES = "RETRIEVING_INTERNAL_SOURCES"
    VALIDATING_SOURCES = "VALIDATING_SOURCES"
    EXECUTING_TOOLS = "EXECUTING_TOOLS"
    RECONCILING_RESULTS = "RECONCILING_RESULTS"
    GENERATING_STRUCTURED_RESULT = "GENERATING_STRUCTURED_RESULT"
    QUALITY_GATE = "QUALITY_GATE"
    COMPLETED = "COMPLETED"

    # Terminal / Alternative States
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    REJECTED_BY_POLICY = "REJECTED_BY_POLICY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    AWAITING_HUMAN_REVIEW = "AWAITING_HUMAN_REVIEW"


TERMINAL_STATES = {
    AnalysisJobStatus.COMPLETED,
    AnalysisJobStatus.REJECTED_BY_POLICY,
    AnalysisJobStatus.FAILED,
    AnalysisJobStatus.CANCELLED,
    AnalysisJobStatus.EXPIRED,
    AnalysisJobStatus.BUDGET_EXCEEDED,
}

VALID_TRANSITIONS: dict[AnalysisJobStatus, set[AnalysisJobStatus]] = {
    AnalysisJobStatus.RECEIVED: {
        AnalysisJobStatus.UNDERSTANDING_REQUEST,
        AnalysisJobStatus.CANCELLED,
    },
    AnalysisJobStatus.UNDERSTANDING_REQUEST: {
        AnalysisJobStatus.NEEDS_CLARIFICATION,
        AnalysisJobStatus.PLANNING,
        AnalysisJobStatus.REJECTED_BY_POLICY,
        AnalysisJobStatus.FAILED,
        AnalysisJobStatus.CANCELLED,
    },
    AnalysisJobStatus.NEEDS_CLARIFICATION: {
        AnalysisJobStatus.UNDERSTANDING_REQUEST,
        AnalysisJobStatus.EXPIRED,
        AnalysisJobStatus.CANCELLED,
        AnalysisJobStatus.FAILED,
    },
    AnalysisJobStatus.PLANNING: {
        AnalysisJobStatus.POLICY_CHECK,
        AnalysisJobStatus.FAILED,
        AnalysisJobStatus.CANCELLED,
    },
    AnalysisJobStatus.POLICY_CHECK: {
        AnalysisJobStatus.RETRIEVING_INTERNAL_SOURCES,
        AnalysisJobStatus.REJECTED_BY_POLICY,
        AnalysisJobStatus.FAILED,
        AnalysisJobStatus.CANCELLED,
    },
    AnalysisJobStatus.RETRIEVING_INTERNAL_SOURCES: {
        AnalysisJobStatus.VALIDATING_SOURCES,
        AnalysisJobStatus.FAILED,
        AnalysisJobStatus.BUDGET_EXCEEDED,
        AnalysisJobStatus.CANCELLED,
    },
    AnalysisJobStatus.VALIDATING_SOURCES: {
        AnalysisJobStatus.EXECUTING_TOOLS,
        AnalysisJobStatus.NEEDS_CLARIFICATION,
        AnalysisJobStatus.FAILED,
        AnalysisJobStatus.CANCELLED,
    },
    AnalysisJobStatus.EXECUTING_TOOLS: {
        AnalysisJobStatus.RECONCILING_RESULTS,
        AnalysisJobStatus.FAILED,
        AnalysisJobStatus.BUDGET_EXCEEDED,
        AnalysisJobStatus.CANCELLED,
    },
    AnalysisJobStatus.RECONCILING_RESULTS: {
        AnalysisJobStatus.GENERATING_STRUCTURED_RESULT,
        AnalysisJobStatus.FAILED,
        AnalysisJobStatus.CANCELLED,
    },
    AnalysisJobStatus.GENERATING_STRUCTURED_RESULT: {
        AnalysisJobStatus.QUALITY_GATE,
        AnalysisJobStatus.FAILED,
        AnalysisJobStatus.CANCELLED,
    },
    AnalysisJobStatus.QUALITY_GATE: {
        AnalysisJobStatus.COMPLETED,
        AnalysisJobStatus.AWAITING_HUMAN_REVIEW,
        AnalysisJobStatus.FAILED,
        AnalysisJobStatus.CANCELLED,
    },
    AnalysisJobStatus.AWAITING_HUMAN_REVIEW: {
        AnalysisJobStatus.COMPLETED,
        AnalysisJobStatus.REJECTED_BY_POLICY,
        AnalysisJobStatus.FAILED,
        AnalysisJobStatus.CANCELLED,
    },
}


class AnalysisStateMachine:
    """Sole authoritative state machine managing all AnalysisJob status transitions."""

    @staticmethod
    def validate_transition(current_status: AnalysisJobStatus, new_status: AnalysisJobStatus) -> None:
        if current_status in TERMINAL_STATES:
            raise OrchestrationException(
                "TERMINAL_STATE_MUTATION_PROHIBITED",
                f"Cannot transition from terminal state '{current_status.value}' to '{new_status.value}'.",
            )

        allowed = VALID_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise OrchestrationException(
                "INVALID_STATE_TRANSITION",
                f"Invalid transition from '{current_status.value}' to '{new_status.value}'.",
            )
