from dataclasses import dataclass
from decimal import Decimal

from services.api.app.orchestration.exceptions import AnalysisBudgetExceededException


@dataclass
class JobBudgetTracker:
    max_model_invocations: int = 3
    max_tool_calls: int = 5
    max_tool_depth: int = 2
    max_prompt_tokens: int = 8000
    max_completion_tokens: int = 2000
    max_cost_usd: Decimal = Decimal("0.1000")

    current_model_invocations: int = 0
    current_tool_calls: int = 0
    current_tool_depth: int = 0
    current_prompt_tokens: int = 0
    current_completion_tokens: int = 0
    current_cost_usd: Decimal = Decimal("0.0000")

    def record_model_invocation(self, prompt_tokens: int, completion_tokens: int, cost_usd: Decimal) -> None:
        self.current_model_invocations += 1
        self.current_prompt_tokens += prompt_tokens
        self.current_completion_tokens += completion_tokens
        self.current_cost_usd += cost_usd

        self.verify_budget()

    def record_tool_call(self) -> None:
        self.current_tool_calls += 1
        self.verify_budget()

    def verify_budget(self) -> None:
        if self.current_model_invocations > self.max_model_invocations:
            raise AnalysisBudgetExceededException(
                f"Model invocations ({self.current_model_invocations}) exceeded limit ({self.max_model_invocations})."
            )
        if self.current_tool_calls > self.max_tool_calls:
            raise AnalysisBudgetExceededException(
                f"Tool calls ({self.current_tool_calls}) exceeded limit ({self.max_tool_calls})."
            )
        if self.current_prompt_tokens > self.max_prompt_tokens:
            raise AnalysisBudgetExceededException(
                f"Prompt tokens ({self.current_prompt_tokens}) exceeded limit ({self.max_prompt_tokens})."
            )
        if self.current_completion_tokens > self.max_completion_tokens:
            raise AnalysisBudgetExceededException(
                f"Completion tokens ({self.current_completion_tokens}) exceeded limit ({self.max_completion_tokens})."
            )
        if self.current_cost_usd > self.max_cost_usd:
            raise AnalysisBudgetExceededException(
                f"Cost (${self.current_cost_usd}) exceeded limit (${self.max_cost_usd})."
            )
