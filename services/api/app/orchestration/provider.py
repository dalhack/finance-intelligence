import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from services.api.app.orchestration.exceptions import (
    ModelFailoverProhibitedException,
    ModelProviderNotConfiguredException,
)


@dataclass(frozen=True)
class ModelCapabilities:
    supports_tool_use: bool
    supports_structured_output: bool
    supports_citations: bool
    supports_prompt_caching: bool
    supports_streaming: bool
    supports_multimodal_pdf: bool
    max_context_tokens: int


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    cached_prompt_tokens: int = 0
    estimated_cost_usd: Decimal = Decimal("0.0000")


@dataclass(frozen=True)
class ToolCallRequest:
    tool_call_id: str
    tool_name: str
    arguments_json: dict[str, Any]


@dataclass(frozen=True)
class ModelResponse:
    invocation_id: str
    content_text: str | None
    tool_calls: list[ToolCallRequest]
    stop_reason: str
    token_usage: TokenUsage


class ModelProvider(Protocol):
    def get_capabilities(self) -> ModelCapabilities: ...
    async def invoke_model(self, request: dict[str, Any]) -> ModelResponse: ...


class ProductionProvider:
    """Production provider enforcing fail-closed credential validation and zero-leak policy."""

    def __init__(self, api_key: str | None = None, provider_alias: str = "anthropic"):
        self.provider_alias = provider_alias
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            # Fail closed when external credentials are not supplied
            raise ModelProviderNotConfiguredException(
                "Production provider API key is missing. Execution blocked by external configuration."
            )

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_tool_use=True,
            supports_structured_output=True,
            supports_citations=True,
            supports_prompt_caching=True,
            supports_streaming=True,
            supports_multimodal_pdf=True,
            max_context_tokens=200000,
        )

    async def invoke_model(self, request: dict[str, Any]) -> ModelResponse:
        # Fail-closed in execution since live network model calls are strictly forbidden in Phase 4A
        raise ModelProviderNotConfiguredException(
            "Live production provider API call is prohibited in Phase 4A. Gate: REAL_MODEL_CONNECTION_GATE = BLOCKED_BY_EXTERNAL_CONFIGURATION"
        )


class DeterministicTestModelProvider:
    """Test-only model provider for testing state machine transitions, tool calls, and schema validation.

    STRICTLY PROHIBITED IN PRODUCTION ENVIRONMENT.
    """

    def __init__(self, environment: str = "development"):
        if environment == "production":
            raise ModelFailoverProhibitedException(
                "CRITICAL SECURITY ERROR: DeterministicTestModelProvider is strictly prohibited in production environment."
            )

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_tool_use=True,
            supports_structured_output=True,
            supports_citations=True,
            supports_prompt_caching=True,
            supports_streaming=True,
            supports_multimodal_pdf=True,
            max_context_tokens=128000,
        )

    async def invoke_model(self, request: dict[str, Any]) -> ModelResponse:
        # Deterministic mock response for testing state machine and tool pipeline
        return ModelResponse(
            invocation_id="inv-test-123",
            content_text="Analyzed requested institutions.",
            tool_calls=[
                ToolCallRequest(
                    tool_call_id="call-1",
                    tool_name="compare_institutions",
                    arguments_json={
                        "institution_ids": ["inst-garan", "inst-akbnk"],
                        "reporting_period_ids": ["period-2025-q4"],
                        "semantic_measures": [{"semantic_measure_code": "TOTAL_ASSETS"}],
                        "reporting_basis": "SOLO",
                        "value_source_policy": "BOTH_SEPARATE_SERIES",
                    },
                )
            ],
            stop_reason="tool_use",
            token_usage=TokenUsage(
                prompt_tokens=150,
                completion_tokens=50,
                cached_prompt_tokens=0,
                estimated_cost_usd=Decimal("0.0010"),
            ),
        )
