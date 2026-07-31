import pytest

from services.api.app.orchestration.config import (
    ModelConfigurationInvalidException,
    ModelRegistry,
    ProviderSecretMissingException,
)
from services.api.app.orchestration.provider_anthropic import (
    AnthropicProviderAdapter,
    ModelMaxTokensExceededException,
    ModelRefusalException,
    ModelStopReasonUnsupportedException,
)


def test_anthropic_adapter_capabilities_and_alias():
    adapter = AnthropicProviderAdapter(
        application_model_alias="finance_analysis_balanced",
        use_fake_transport=True,
    )
    caps = adapter.get_capabilities()
    assert caps.supports_tool_use is True
    assert caps.supports_structured_output is True
    assert caps.supports_streaming is True
    assert adapter.config.provider_model_id == "synthetic-test-model"


def test_anthropic_adapter_missing_secret_fail_closed():
    with pytest.raises(ProviderSecretMissingException):
        AnthropicProviderAdapter(
            application_model_alias="finance_analysis_balanced",
            api_key="",
            environment="production",
            use_fake_transport=False,
        )


@pytest.mark.asyncio
async def test_anthropic_adapter_fake_transport_invoke():
    adapter = AnthropicProviderAdapter(
        application_model_alias="finance_analysis_balanced",
        use_fake_transport=True,
    )
    res = await adapter.invoke_model({"messages": []})
    assert res.stop_reason == "tool_use"
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].tool_name == "compare_institutions"

    res_turn2 = await adapter.invoke_model({"messages": [{"role": "user", "content": [{"type": "tool_result"}]}]})
    assert res_turn2.stop_reason == "end_turn"
    assert "Analiz tamamlandı" in str(res_turn2.content_text)


def test_anthropic_adapter_stop_reason_mapping():
    adapter = AnthropicProviderAdapter(use_fake_transport=True)
    assert adapter.map_stop_reason("end_turn") == "end_turn"
    assert adapter.map_stop_reason("tool_use") == "tool_use"

    with pytest.raises(ModelMaxTokensExceededException):
        adapter.map_stop_reason("max_tokens")

    with pytest.raises(ModelRefusalException):
        adapter.map_stop_reason("refusal")

    with pytest.raises(ModelStopReasonUnsupportedException):
        adapter.map_stop_reason("unknown_reason")


def test_model_registry_unknown_alias():
    with pytest.raises(ModelConfigurationInvalidException):
        ModelRegistry.get_config("unknown_alias_123")
