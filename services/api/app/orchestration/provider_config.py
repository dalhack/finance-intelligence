from dataclasses import dataclass


@dataclass
class ProviderRuntimeConfig:
    """Production provider runtime configuration with strict fail-closed validation."""

    provider_type: str = "anthropic"
    balanced_model_alias: str = "finance_analysis_balanced"
    fast_model_alias: str = "finance_analysis_fast"
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 30.0
    max_retries: int = 3
    max_input_tokens: int = 4096
    max_output_tokens: int = 4096
    max_tool_iterations: int = 5
    per_analysis_token_budget: int = 20000
    circuit_breaker_threshold: int = 5
    circuit_open_duration_seconds: int = 60
    tls_verification_enabled: bool = True
    base_url: str | None = None

    def validate_for_environment(self, environment: str = "development") -> None:
        """Validate config properties fail-closed according to environment policy."""
        is_prod = environment.lower() in ("production", "staging", "prod")

        if self.provider_type.lower() not in ("anthropic", "synthetic_test"):
            raise ValueError("MODEL_CONFIGURATION_INVALID: Unsupported provider type")

        if self.connect_timeout_seconds <= 0 or self.read_timeout_seconds <= 0:
            raise ValueError("MODEL_CONFIGURATION_INVALID: Timeout settings must be positive")

        if self.max_input_tokens <= 0 or self.max_output_tokens <= 0:
            raise ValueError("MODEL_CONFIGURATION_INVALID: Token limits must be positive")

        if is_prod:
            if not self.tls_verification_enabled:
                raise ValueError("MODEL_CONFIGURATION_INVALID: TLS verification cannot be disabled in production")
            if self.base_url and ("localhost" in self.base_url or "127.0.0.1" in self.base_url):
                raise ValueError("MODEL_CONFIGURATION_INVALID: Insecure local base_url forbidden in production")

    def __repr__(self) -> str:
        return (
            f"ProviderRuntimeConfig(provider={self.provider_type}, "
            f"balanced_alias={self.balanced_model_alias}, "
            f"tls={self.tls_verification_enabled})"
        )
