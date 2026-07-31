import anthropic
import pytest
from anthropic.types import Message, TextBlock, Usage


@pytest.mark.unit
def test_anthropic_sdk_public_interface_types():
    """Verify that installed anthropic package exports expected public types and async client interfaces."""
    client = anthropic.AsyncAnthropic(api_key="synthetic_test_key")
    assert client is not None

    # Test Message construction with Usage containing prompt, completion, and cache tokens
    usage = Usage(
        input_tokens=100,
        output_tokens=50,
        cache_creation_input_tokens=25,
        cache_read_input_tokens=10,
    )
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.cache_creation_input_tokens == 25
    assert usage.cache_read_input_tokens == 10

    # Test TextBlock
    block = TextBlock(text="Hello", type="text")
    assert block.type == "text"
    assert block.text == "Hello"

    # Test Message object structure
    msg = Message(
        id="msg_123",
        content=[block],
        model="synthetic-test-model",
        role="assistant",
        stop_reason="end_turn",
        stop_sequence=None,
        type="message",
        usage=usage,
    )
    assert msg.id == "msg_123"
    assert msg.stop_reason == "end_turn"
    assert msg.usage.input_tokens == 100
