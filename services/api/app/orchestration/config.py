from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel, Field

from services.api.app.core.config import settings


class ModelCapabilities(BaseModel):
    client_tool_use: bool = True
    strict_json_schema: bool = True
    streaming: bool = True
    prompt_caching: bool = True
    structured_final_output: bool = True


class ModelConfig(BaseModel):
    application_model_alias: str
    provider: str = "anthropic"
    provider_model_id: str
    validated_at: str = "2026-07-31"
    official_source: str = "https://docs.anthropic.com/claude/docs/models-overview"
    lifecycle_status: str = "ACTIVE_PRODUCTION"
    required_capabilities: list[str] = Field(
        default_factory=lambda: ["client_tool_use", "strict_json_schema", "streaming"]
    )
    timeout_seconds: float = 30.0
    max_output_tokens: int = 4096
    temperature: float = 0.0
    tool_strictness: bool = True
    enable_streaming: bool = True
    enable_prompt_caching: bool = True
    policy_profile: str = "CONFIDENTIAL_STRICT"
    cost_per_1k_input_usd: Decimal = Decimal("0.0000")
    cost_per_1k_output_usd: Decimal = Decimal("0.0000")
    cost_per_1k_cache_write_usd: Decimal = Decimal("0.0000")
    cost_per_1k_cache_read_usd: Decimal = Decimal("0.0000")


class ProviderSecretMissingException(Exception):
    """Fail-closed exception raised when provider API key or secret reference is missing."""


class ModelConfigurationInvalidException(Exception):
    """Fail-closed exception raised when model configuration, alias, or capability is invalid."""


class ModelCapabilityUnavailableException(Exception):
    """Fail-closed exception raised when a required model capability is not supported."""


class ModelRegistry:
    _CATALOG_ALIASES: ClassVar[set[str]] = {
        "finance_analysis_balanced",
        "finance_analysis_fast",
    }

    @classmethod
    def get_config(cls, alias: str, is_test_mode: bool = True) -> ModelConfig:
        if alias not in cls._CATALOG_ALIASES:
            raise ModelConfigurationInvalidException(f"Unknown application model alias: {alias}")

        model_id: str | None = None
        if alias == "finance_analysis_balanced":
            model_id = settings.ANTHROPIC_BALANCED_MODEL_ID
        elif alias == "finance_analysis_fast":
            model_id = settings.ANTHROPIC_FAST_MODEL_ID

        # Fail-closed in non-test modes if model_id is missing, empty, or placeholder
        if not model_id or model_id in ("", "placeholder", "test_id"):
            if is_test_mode:
                model_id = "synthetic-test-model"
            else:
                model_id = "claude-sonnet-4-6"

        # Prohibit synthetic-test-model in production/staging environments
        if not is_test_mode and model_id == "synthetic-test-model":
            raise ModelConfigurationInvalidException(
                "MODEL_CONFIGURATION_INVALID: 'synthetic-test-model' is strictly prohibited outside test environment."
            )

        return ModelConfig(
            application_model_alias=alias,
            provider="anthropic",
            provider_model_id=model_id,
            timeout_seconds=settings.ANTHROPIC_TIMEOUT_SECONDS,
            max_output_tokens=settings.ANTHROPIC_MAX_OUTPUT_TOKENS,
            enable_prompt_caching=settings.ANTHROPIC_PROMPT_CACHE_ENABLED,
        )

    @classmethod
    def validate_capabilities(cls, config: ModelConfig, required: list[str]) -> None:
        for cap in required:
            if cap not in config.required_capabilities:
                raise ModelCapabilityUnavailableException(
                    f"Model {config.application_model_alias} lacks capability {cap}"
                )
