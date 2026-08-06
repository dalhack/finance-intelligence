import hashlib
import os
from decimal import Decimal
from typing import Any
from uuid import uuid4

from services.api.app.orchestration.config import (
    ModelConfig,
    ModelRegistry,
    ProviderSecretMissingException,
)
from services.api.app.orchestration.provider import (
    ModelCapabilities,
    ModelResponse,
    TokenUsage,
    ToolCallRequest,
)


class ModelMaxTokensExceededException(Exception):
    """Exception raised when model output stops due to max_tokens."""


class ModelRefusalException(Exception):
    """Exception raised when model refuses request due to safety policies."""


class ModelStopReasonUnsupportedException(Exception):
    """Exception raised when model output contains an unsupported or unknown stop reason."""


class AnthropicProviderAdapter:
    """Production & Synthetic Test Adapter for Anthropic Messages API.

    Enforces fail-closed credential validation, deterministic fake transport for testing,
    application alias mapping, tool_use mapping, and stop_reason classification.
    """

    def __init__(
        self,
        application_model_alias: str = "finance_analysis_balanced",
        api_key: str | None = None,
        environment: str = "development",
        use_fake_transport: bool = False,
    ):
        self.application_model_alias = application_model_alias
        self.config: ModelConfig = ModelRegistry.get_config(application_model_alias)
        self.environment = environment
        self.use_fake_transport = use_fake_transport

        # Resolve secret reference
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        if (
            not self.use_fake_transport
            and (not self.api_key or self.api_key in ("placeholder", "test_key", ""))
            and environment == "production"
        ):
            raise ProviderSecretMissingException(
                "Production Anthropic API key is missing or invalid. Execution fail-closed."
            )

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_tool_use=True,
            supports_structured_output=True,
            supports_citations=True,
            supports_prompt_caching=self.config.enable_prompt_caching,
            supports_streaming=self.config.enable_streaming,
            supports_multimodal_pdf=True,
            max_context_tokens=200000,
        )

    def hash_request_id(self, provider_req_id: str) -> str:
        """Compute safe hash fingerprint of provider request ID for audit logging."""
        return hashlib.sha256(provider_req_id.encode("utf-8")).hexdigest()[:16]

    async def invoke_model(self, request: dict[str, Any]) -> ModelResponse:
        if self.use_fake_transport:
            return await self._execute_fake_transport(request)

        if not self.api_key or self.api_key in ("placeholder", "test_key", ""):
            raise ProviderSecretMissingException("Anthropic API key is missing or invalid.")

        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        model_name = self.config.provider_model_id
        system_prompt = request.get("system", "You are an expert financial analysis assistant.")
        messages = request.get("messages", [])
        tools = request.get("tools")

        kwargs: dict[str, Any] = {
            "model": model_name,
            "max_tokens": request.get("max_tokens", 1024),
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = tools

        response = await client.messages.create(**kwargs)

        content_text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCallRequest(
                        tool_call_id=block.id,
                        tool_name=block.name,
                        arguments_json=block.input if isinstance(block.input, dict) else {},
                    )
                )

        return ModelResponse(
            invocation_id=response.id,
            content_text=content_text,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "end_turn",
            token_usage=TokenUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                cached_prompt_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
                estimated_cost_usd=Decimal("0.00"),
            ),
        )

    async def _execute_fake_transport(self, request: dict[str, Any]) -> ModelResponse:
        inv_id = f"inv-{uuid4().hex[:12]}"
        messages = request.get("messages", [])

        # Check if previous turn had tool_results
        has_tool_results = any(
            isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), list) for m in messages
        )

        if not has_tool_results:
            # Turn 1: Return tool_use call for compare_institutions
            return ModelResponse(
                invocation_id=inv_id,
                content_text="Starting financial institution analysis.",
                tool_calls=[
                    ToolCallRequest(
                        tool_call_id="call_compare_001",
                        tool_name="compare_institutions",
                        arguments_json={
                            "institution_ids": request.get("institution_ids", ["11111111-1111-1111-1111-111111111111"]),
                            "reporting_period_ids": request.get(
                                "reporting_period_ids", ["22222222-2222-2222-2222-222222222222"]
                            ),
                            "semantic_measures": [{"semantic_measure_code": "TOTAL_ASSETS"}],
                        },
                    )
                ],
                stop_reason="tool_use",
                token_usage=TokenUsage(
                    prompt_tokens=250,
                    completion_tokens=80,
                    cached_prompt_tokens=100,
                    estimated_cost_usd=Decimal("0.0012"),
                ),
            )
        else:
            # Turn 2: Return final structured completion (end_turn)
            return ModelResponse(
                invocation_id=inv_id,
                content_text="Analiz tamamlandı. Garanti BBVA 2025 Q4 Toplam Aktif tutarı 1,500,000 TRY olarak doğrulanmıştır.",
                tool_calls=[],
                stop_reason="end_turn",
                token_usage=TokenUsage(
                    prompt_tokens=400,
                    completion_tokens=150,
                    cached_prompt_tokens=150,
                    estimated_cost_usd=Decimal("0.0025"),
                ),
            )

    def map_stop_reason(self, stop_reason_raw: str) -> str:
        match stop_reason_raw:
            case "end_turn":
                return "end_turn"
            case "tool_use":
                return "tool_use"
            case "max_tokens":
                raise ModelMaxTokensExceededException("MODEL_MAX_TOKENS_EXCEEDED")
            case "refusal":
                raise ModelRefusalException("MODEL_REFUSAL")
            case _:
                raise ModelStopReasonUnsupportedException("MODEL_STOP_REASON_UNSUPPORTED")
