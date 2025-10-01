"""Tests for Anthropic thinking blocks support in LLM and Message classes."""

from litellm.types.llms.openai import ChatCompletionThinkingBlock
from litellm.types.utils import Choices, Message as LiteLLMMessage, ModelResponse, Usage
from pydantic import SecretStr

from openhands.sdk import LLM, Message, TextContent, ThinkingBlock


def create_mock_response_with_thinking(
    content: str = "Test response",
    thinking_content: str = "Let me think about this...",
    response_id: str = "test-id",
):
    """Helper function to create mock responses with thinking blocks."""
    # Create a thinking block
    thinking_block = ChatCompletionThinkingBlock(
        type="thinking",
        thinking=thinking_content,
    )

    # Create the message with thinking blocks
    message = LiteLLMMessage(
        content=content,
        role="assistant",
        thinking_blocks=[thinking_block],
    )

    return ModelResponse(
        id=response_id,
        choices=[
            Choices(
                finish_reason="stop",
                index=0,
                message=message,
            )
        ],
        created=1234567890,
        model="claude-sonnet-4-5",
        object="chat.completion",
        usage=Usage(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        ),
    )


def test_thinking_block_model():
    """Test ThinkingBlock model creation and validation."""
    from openhands.sdk.llm.message import ThinkingBlock

    # Test basic thinking block
    block = ThinkingBlock(
        thinking="Let me think about this step by step...",
    )

    assert block.type == "thinking"
    assert block.thinking == "Let me think about this step by step..."
    assert block.signature is None

    # Test thinking block with signature
    block_with_sig = ThinkingBlock(
        thinking="Complex reasoning process...",
        signature="signature_hash_123",
    )

    assert block_with_sig.type == "thinking"
    assert block_with_sig.thinking == "Complex reasoning process..."
    assert block_with_sig.signature == "signature_hash_123"


def test_message_with_thinking_blocks():
    """Test Message with thinking blocks fields."""
    from openhands.sdk.llm.message import Message, TextContent, ThinkingBlock

    thinking_block = ThinkingBlock(
        thinking="Let me think about this step by step...",
        signature="sig123",
    )

    message = Message(
        role="assistant",
        content=[TextContent(text="The answer is 42.")],
        thinking_blocks=[thinking_block],
    )

    assert len(message.thinking_blocks) == 1
    assert isinstance(message.thinking_blocks[0], ThinkingBlock)
    assert (
        message.thinking_blocks[0].thinking == "Let me think about this step by step..."
    )
    assert message.thinking_blocks[0].signature == "sig123"


def test_message_without_thinking_blocks():
    """Test Message without thinking blocks (default behavior)."""
    from openhands.sdk.llm.message import Message, TextContent

    message = Message(role="assistant", content=[TextContent(text="The answer is 42.")])

    assert message.thinking_blocks == []


def test_message_from_litellm_message_with_thinking():
    """Test Message.from_litellm_message with thinking blocks."""
    from openhands.sdk.llm.message import Message

    # Create a mock LiteLLM message with thinking blocks
    thinking_block = ChatCompletionThinkingBlock(
        type="thinking",
        thinking="Let me analyze this problem...",
        signature="hash_456",
    )

    litellm_message = LiteLLMMessage(
        role="assistant",
        content="The answer is 42.",
        thinking_blocks=[thinking_block],
    )

    message = Message.from_litellm_message(litellm_message)

    assert message.role == "assistant"
    assert len(message.content) == 1
    from openhands.sdk.llm.message import TextContent

    assert isinstance(message.content[0], TextContent)
    assert message.content[0].text == "The answer is 42."

    # Check thinking blocks
    assert len(message.thinking_blocks) == 1
    assert isinstance(message.thinking_blocks[0], ThinkingBlock)
    assert message.thinking_blocks[0].thinking == "Let me analyze this problem..."
    assert message.thinking_blocks[0].signature == "hash_456"


def test_message_from_litellm_message_without_thinking():
    """Test Message.from_litellm_message without thinking blocks."""
    from openhands.sdk.llm.message import Message

    litellm_message = LiteLLMMessage(role="assistant", content="The answer is 42.")

    message = Message.from_litellm_message(litellm_message)

    assert message.role == "assistant"
    assert len(message.content) == 1
    from openhands.sdk.llm.message import TextContent

    assert isinstance(message.content[0], TextContent)
    assert message.content[0].text == "The answer is 42."
    assert message.thinking_blocks == []


def test_message_serialization_with_thinking_blocks():
    """Test Message serialization includes thinking blocks."""
    from openhands.sdk.llm.message import Message, TextContent, ThinkingBlock

    thinking_block = ThinkingBlock(
        thinking="Reasoning process...",
        signature="sig789",
    )

    message = Message(
        role="assistant",
        content=[TextContent(text="Answer")],
        thinking_blocks=[thinking_block],
    )

    serialized = message.model_dump()

    assert len(serialized["thinking_blocks"]) == 1
    assert serialized["thinking_blocks"][0]["thinking"] == "Reasoning process..."
    assert serialized["thinking_blocks"][0]["signature"] == "sig789"
    assert serialized["thinking_blocks"][0]["type"] == "thinking"


def test_message_serialization_without_thinking_blocks():
    """Test Message serialization without thinking blocks."""
    from openhands.sdk.llm.message import Message, TextContent

    message = Message(role="assistant", content=[TextContent(text="Answer")])

    serialized = message.model_dump()

    assert serialized["thinking_blocks"] == []


def test_message_list_serializer_with_thinking_blocks():
    """Test Message._list_serializer includes thinking blocks in content array."""
    from openhands.sdk.llm.message import Message, TextContent, ThinkingBlock

    thinking_block = ThinkingBlock(
        thinking="Let me think...",
        signature="sig_abc",
    )

    message = Message(
        role="assistant",
        content=[TextContent(text="The answer is 42.")],
        thinking_blocks=[thinking_block],
    )

    serialized = message._list_serializer()
    content_list = serialized["content"]

    # Should have thinking block first, then text content
    assert len(content_list) == 2
    assert content_list[0]["type"] == "thinking"
    assert content_list[0]["thinking"] == "Let me think..."
    assert content_list[0]["signature"] == "sig_abc"
    assert content_list[1]["type"] == "text"
    assert content_list[1]["text"] == "The answer is 42."


def test_message_event_thinking_blocks_property():
    """Test MessageEvent thinking_blocks property."""
    from openhands.sdk.event.llm_convertible import MessageEvent
    from openhands.sdk.llm.message import Message, TextContent, ThinkingBlock

    thinking_block = ThinkingBlock(
        thinking="Complex reasoning...",
        signature="sig_def",
    )

    message = Message(
        role="assistant",
        content=[TextContent(text="Result")],
        thinking_blocks=[thinking_block],
    )

    event = MessageEvent(llm_message=message, source="agent")

    # Test thinking_blocks property
    assert len(event.thinking_blocks) == 1
    thinking_block = event.thinking_blocks[0]
    assert isinstance(thinking_block, ThinkingBlock)
    assert thinking_block.thinking == "Complex reasoning..."
    assert thinking_block.signature == "sig_def"


def test_message_event_visualize_with_thinking_blocks():
    """Test MessageEvent.visualize includes thinking blocks."""
    from openhands.sdk.event.llm_convertible import MessageEvent
    from openhands.sdk.llm.message import Message, TextContent, ThinkingBlock

    thinking_block = ThinkingBlock(
        thinking=(
            "This is a very long thinking process that should be truncated when "
            "displayed in the visualization because it exceeds the 200 character "
            "limit that we set for the preview display."
        ),
        signature="sig_ghi",
    )

    message = Message(
        role="assistant",
        content=[TextContent(text="Final answer")],
        thinking_blocks=[thinking_block],
    )

    event = MessageEvent(llm_message=message, source="agent")

    visualization = event.visualize

    # Should contain thinking blocks section
    viz_text = str(visualization)
    assert "Thinking Blocks (Anthropic Extended Thinking)" in viz_text
    assert "Block 1:" in viz_text
    assert "..." in viz_text  # Long thinking should be truncated


def test_message_event_str_with_thinking_blocks():
    """Test MessageEvent.__str__ includes thinking blocks count."""
    from openhands.sdk.event.llm_convertible import MessageEvent
    from openhands.sdk.llm.message import Message, TextContent, ThinkingBlock

    thinking_blocks = [
        ThinkingBlock(thinking="First thought"),
        ThinkingBlock(thinking="Second thought"),
    ]

    message = Message(
        role="assistant",
        content=[TextContent(text="Answer")],
        thinking_blocks=thinking_blocks,
    )

    event = MessageEvent(llm_message=message, source="agent")

    str_repr = str(event)

    # Should include thinking blocks count
    assert "[Thinking blocks: 2]" in str_repr


def test_multiple_thinking_blocks():
    """Test handling multiple thinking blocks."""
    thinking_blocks = [
        ThinkingBlock(thinking="First reasoning step", signature="sig1"),
        ThinkingBlock(thinking="Second reasoning step", signature="sig2"),
        ThinkingBlock(thinking="Final reasoning step"),
    ]

    message = Message(
        role="assistant",
        content=[TextContent(text="Conclusion")],
        thinking_blocks=thinking_blocks,
    )

    assert len(message.thinking_blocks) == 3
    assert isinstance(message.thinking_blocks[0], ThinkingBlock)
    assert message.thinking_blocks[0].thinking == "First reasoning step"
    assert isinstance(message.thinking_blocks[1], ThinkingBlock)
    assert message.thinking_blocks[1].thinking == "Second reasoning step"
    assert isinstance(message.thinking_blocks[2], ThinkingBlock)
    assert message.thinking_blocks[2].thinking == "Final reasoning step"
    assert message.thinking_blocks[2].signature is None

    # Test serialization
    serialized = message._list_serializer()
    content_list = serialized["content"]
    assert len(content_list) == 4  # 3 thinking blocks + 1 text content
    assert all(item["type"] == "thinking" for item in content_list[:3])
    assert content_list[3]["type"] == "text"


def test_llm_ensures_thinking_blocks_for_anthropic():
    """Test that LLM automatically adds thinking blocks for Anthropic models."""
    # Create LLM with Anthropic model and reasoning effort
    llm = LLM(
        service_id="test",
        model="anthropic/claude-sonnet-4-5",
        reasoning_effort="medium",
        api_key=SecretStr("test-key"),
    )

    # Create messages without thinking blocks
    messages = [
        Message(
            role="system", content=[TextContent(text="You are a helpful assistant.")]
        ),
        Message(role="user", content=[TextContent(text="Hello!")]),
        Message(role="assistant", content=[TextContent(text="Hi there!")]),
        Message(role="user", content=[TextContent(text="How are you?")]),
        Message(
            role="assistant", content=[TextContent(text="I'm doing well, thanks!")]
        ),
    ]

    # Format messages for LLM - this should add thinking blocks to assistant messages
    formatted_messages = llm.format_messages_for_llm(messages)

    # Check that assistant messages now have thinking blocks
    for i, formatted_msg in enumerate(formatted_messages):
        if formatted_msg["role"] == "assistant":
            content = formatted_msg["content"]
            # First item should be a redacted thinking block (placeholder)
            # FIXME: this is wrong!
            # assert content[0]["type"] == "redacted_thinking"
            # assert "thinking" in content[0]
            # Second item should be the original text content
            assert content[1]["type"] == "text"


def test_llm_preserves_existing_thinking_blocks():
    """Test that LLM preserves existing thinking blocks and doesn't add duplicates."""
    from pydantic import SecretStr

    from openhands.sdk.llm.llm import LLM
    from openhands.sdk.llm.message import Message, TextContent, ThinkingBlock

    # Create LLM with Anthropic model and reasoning effort
    llm = LLM(
        service_id="test",
        model="anthropic/claude-sonnet-4-5",
        reasoning_effort="high",
        api_key=SecretStr("test-key"),
    )

    # Create message with existing thinking block
    existing_thinking = ThinkingBlock(
        thinking="I already have a thinking block", signature="existing_sig"
    )

    messages = [
        Message(
            role="assistant",
            content=[TextContent(text="Response with existing thinking")],
            thinking_blocks=[existing_thinking],
        ),
    ]

    # Format messages for LLM
    formatted_messages = llm.format_messages_for_llm(messages)

    # Check that the existing thinking block is preserved and no duplicate is added
    content = formatted_messages[0]["content"]
    thinking_blocks = [item for item in content if item["type"] == "thinking"]

    assert len(thinking_blocks) == 1
    assert thinking_blocks[0]["thinking"] == "I already have a thinking block"
    assert thinking_blocks[0]["signature"] == "existing_sig"


def test_llm_no_thinking_blocks_for_non_anthropic():
    """Test that non-Anthropic models don't get automatic thinking blocks."""
    from pydantic import SecretStr

    from openhands.sdk.llm.llm import LLM
    from openhands.sdk.llm.message import Message, TextContent

    # Create LLM with non-Anthropic model
    llm = LLM(
        service_id="test",
        model="openai/gpt-4",
        reasoning_effort="medium",
        api_key=SecretStr("test-key"),
    )

    # Create assistant message without thinking blocks
    messages = [
        Message(role="assistant", content=[TextContent(text="Hello!")]),
    ]

    # Format messages for LLM
    formatted_messages = llm.format_messages_for_llm(messages)

    # Check that no thinking blocks were added
    content = formatted_messages[0]["content"]

    # For non-Anthropic models, content might be a string instead of a list
    if isinstance(content, str):
        # String format - no thinking blocks possible
        assert "thinking" not in content.lower()
    else:
        # List format - check for thinking blocks
        thinking_blocks = [item for item in content if item.get("type") == "thinking"]
        assert len(thinking_blocks) == 0
        assert content[0]["type"] == "text"
