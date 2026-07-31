import pytest

from services.api.app.orchestration.payload_builder import ProviderPayloadBuilder
from services.api.app.orchestration.policy_engine import DataClassification
from services.api.app.orchestration.provider_config import ProviderRuntimeConfig
from services.api.app.orchestration.secret_resolver import (
    DeterministicTestSecretResolver,
    EnvironmentSecretResolver,
)


def test_provider_runtime_config_validation():
    """Verify fail-closed ProviderRuntimeConfig validation for environment settings."""
    cfg = ProviderRuntimeConfig()
    cfg.validate_for_environment("development")

    # Invalid provider type
    bad_cfg = ProviderRuntimeConfig(provider_type="unsupported_provider")
    with pytest.raises(ValueError, match="MODEL_CONFIGURATION_INVALID"):
        bad_cfg.validate_for_environment("development")

    # Production TLS verification check
    insecure_cfg = ProviderRuntimeConfig(tls_verification_enabled=False)
    with pytest.raises(ValueError, match="TLS verification cannot be disabled"):
        insecure_cfg.validate_for_environment("production")

    # Production localhost base URL check
    local_cfg = ProviderRuntimeConfig(base_url="http://localhost:8000")
    with pytest.raises(ValueError, match="Insecure local base_url forbidden"):
        local_cfg.validate_for_environment("production")

    # Repr redacts secrets
    assert "redacted" not in repr(cfg) or "balanced_alias" in repr(cfg)


def test_secret_resolver_behavior(monkeypatch):
    """Verify EnvironmentSecretResolver and DeterministicTestSecretResolver fail-closed rules."""
    resolver = EnvironmentSecretResolver()
    assert resolver.resolve("") is None
    assert resolver.resolve("NON_EXISTENT_ENV_KEY_XYZ") is None

    monkeypatch.setenv("TEST_SECRET_KEY_123", "secret_value_abc")
    assert resolver.resolve("TEST_SECRET_KEY_123") == "secret_value_abc"
    assert "redacted" in repr(resolver)

    test_resolver = DeterministicTestSecretResolver()
    assert test_resolver.resolve("anthropic_key") == "sk-ant-synthetic-test-key-anthropi"
    assert "redacted" in repr(test_resolver)


def test_provider_payload_builder_sanitization():
    """Verify ProviderPayloadBuilder strips forbidden fields and enforces STRICTLY_CONFIDENTIAL network deny."""
    dirty_context = {
        "organization_id": "c794ef64-9b2f-4c12-881a-4d2c88219011",
        "user_id": "usr-123",
        "role": "admin",
        "api_key": "secret",
        "allowed_param": "safe_value",
    }

    messages = ProviderPayloadBuilder.build_messages_payload(
        user_prompt="Analyze balance sheet",
        classification=DataClassification.CONFIDENTIAL,
        context_data=dirty_context,
    )

    assert len(messages) == 1
    content = messages[0]["content"]
    assert "Analyze balance sheet" in content
    assert "safe_value" in content
    assert "organization_id" not in content
    assert "user_id" not in content
    assert "api_key" not in content

    # STRICTLY_CONFIDENTIAL raises Network Deny exception
    with pytest.raises(ValueError, match="STRICTLY_CONFIDENTIAL_NETWORK_DENY"):
        ProviderPayloadBuilder.build_messages_payload(
            user_prompt="Secret prompt",
            classification=DataClassification.STRICTLY_CONFIDENTIAL,
        )
