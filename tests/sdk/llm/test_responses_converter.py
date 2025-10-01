"""Tests for responses converter utilities."""

from typing import Any, cast

from litellm.types.llms.openai import ResponsesAPIResponse as Response
from litellm.types.utils import ModelResponse

from openhands.sdk.llm.utils.responses_converter import (
    messages_to_responses_items,
    responses_to_completion_format,
)


def test_messages_to_responses_input_empty():
    assert messages_to_responses_items([]) == []


def test_messages_to_responses_order_assistant_text_before_function_call():
    from openhands.sdk.llm.message import Message, TextContent

    msgs_typed = [
        Message(
            role="assistant",
            content=[TextContent(text="thinking...")],
            tool_calls=[
                __import__("typing").cast(
                    Any,
                    __import__("litellm").types.utils.ChatCompletionMessageToolCall(
                        id="call_1",
                        type="function",
                        function=__import__("litellm").types.utils.Function(
                            name="echo", arguments='{"s":"hi"}'
                        ),
                    ),
                )
            ],
        ).to_llm_dict(),
        Message(
            role="tool", content=[TextContent(text="hi")], tool_call_id="call_1"
        ).to_llm_dict(),
    ]
    items = messages_to_responses_items(msgs_typed)
    items = cast(list[dict[str, Any]], items)
    # Expect ordering: assistant text, then function_call, then function_call_output
    assert items[0] == {"role": "assistant", "content": "thinking..."}
    assert items[1]["type"] == "function_call" and items[1]["call_id"] == "call_1"
    assert (
        items[2]["type"] == "function_call_output" and items[2]["call_id"] == "call_1"
    )

    from openhands.sdk.llm.message import Message, TextContent

    msgs_typed = [
        Message(
            role="assistant",
            content=[TextContent(text="thinking...")],
            tool_calls=[
                __import__("typing").cast(
                    Any,
                    __import__("litellm").types.utils.ChatCompletionMessageToolCall(
                        id="call_1",
                        type="function",
                        function=__import__("litellm").types.utils.Function(
                            name="echo", arguments='{"s":"hi"}'
                        ),
                    ),
                )
            ],
        ).to_llm_dict(),
        Message(
            role="tool", content=[TextContent(text="hi")], tool_call_id="call_1"
        ).to_llm_dict(),
    ]
    items = messages_to_responses_items(msgs_typed)
    items = cast(list[dict[str, Any]], items)
    # Expect ordering: assistant text, then function_call, then function_call_output
    assert items[0] == {"role": "assistant", "content": "thinking..."}
    assert items[1]["type"] == "function_call" and items[1]["call_id"] == "call_1"
    assert (
        items[2]["type"] == "function_call_output" and items[2]["call_id"] == "call_1"
    )


def test_messages_to_responses_input_typed_messages():
    from openhands.sdk.llm.message import Message, TextContent

    msgs_typed = [
        Message(role="system", content=[TextContent(text="S")]).to_llm_dict(),
        Message(role="user", content=[TextContent(text="U")]).to_llm_dict(),
        Message(role="assistant", content=[TextContent(text="A")]).to_llm_dict(),
    ]
    assert messages_to_responses_items(msgs_typed) == [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "U"},
        {"role": "assistant", "content": "A"},
    ]


def test_messages_to_responses_input_with_tool_message():
    from litellm.types.utils import ChatCompletionMessageToolCall, Function

    from openhands.sdk.llm.message import Message, TextContent

    msgs = [
        Message(
            role="assistant",
            content=[TextContent(text="")],
            tool_calls=[
                ChatCompletionMessageToolCall(
                    id="call_1",
                    type="function",
                    function=Function(name="f", arguments='{"a":1}'),
                )
            ],
        ).to_llm_dict(),
        Message(
            role="tool", content=[TextContent(text="out")], tool_call_id="call_1"
        ).to_llm_dict(),
    ]
    items = messages_to_responses_items(msgs)
    items = cast(list[dict[str, Any]], items)
    assert {
        "type": "function_call",
        "call_id": "call_1",
        "name": "f",
        "arguments": '{"a":1}',
    } in items
    assert {
        "type": "function_call_output",
        "call_id": "call_1",
        "output": "out",
    } in items


def test_messages_to_responses_input_message_objects():
    from openhands.sdk.llm.message import Message, TextContent

    msgs = [
        Message(role="user", content=[TextContent(text="Hello")]).to_llm_dict(),
        Message(role="assistant", content=[TextContent(text="Hi")]).to_llm_dict(),
    ]
    assert messages_to_responses_items(msgs) == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]


def test_messages_to_responses_input_with_images():
    """Test conversion of messages with image content to Responses format."""
    from openhands.sdk.llm.message import ImageContent, Message, TextContent

    msgs = [
        Message(
            role="user",
            content=[
                TextContent(text="What's in this image?"),
                ImageContent(image_urls=["data:image/png;base64,abc123"]),
            ],
            vision_enabled=True,
        ).to_llm_dict()
    ]
    items = messages_to_responses_items(msgs)
    items = cast(list[dict[str, Any]], items)

    # Should produce two items: one text message and one image input
    assert len(items) == 2
    assert items[0] == {"role": "user", "content": "What's in this image?"}
    assert items[1] == {
        "type": "input_image",
        "image_url": "data:image/png;base64,abc123",
    }


def test_messages_to_responses_input_with_multiple_images():
    """Test conversion of messages with multiple images."""
    from openhands.sdk.llm.message import ImageContent, Message, TextContent

    msgs = [
        Message(
            role="user",
            content=[
                TextContent(text="Compare these images:"),
                ImageContent(
                    image_urls=[
                        "data:image/png;base64,image1",
                        "data:image/jpeg;base64,image2",
                    ]
                ),
                TextContent(text="Which is better?"),
            ],
            vision_enabled=True,
        ).to_llm_dict()
    ]
    items = messages_to_responses_items(msgs)
    items = cast(list[dict[str, Any]], items)

    # Should produce four items: text, image, image, text
    assert len(items) == 4
    assert items[0] == {"role": "user", "content": "Compare these images:"}
    assert items[1] == {
        "type": "input_image",
        "image_url": "data:image/png;base64,image1",
    }
    assert items[2] == {
        "type": "input_image",
        "image_url": "data:image/jpeg;base64,image2",
    }
    assert items[3] == {"role": "user", "content": "Which is better?"}


def test_messages_to_responses_input_image_only():
    """Test conversion of messages with only image content."""
    from openhands.sdk.llm.message import ImageContent, Message

    msgs = [
        Message(
            role="user",
            content=[ImageContent(image_urls=["https://example.com/image.jpg"])],
            vision_enabled=True,
        ).to_llm_dict()
    ]
    items = messages_to_responses_items(msgs)
    items = cast(list[dict[str, Any]], items)

    # Should produce one image input item
    assert len(items) == 1
    assert items[0] == {
        "type": "input_image",
        "image_url": "https://example.com/image.jpg",
    }


def test_messages_to_responses_input_mixed_content_with_tools():
    """Test conversion with mixed text/image content and tool calls."""
    from litellm.types.utils import ChatCompletionMessageToolCall, Function

    from openhands.sdk.llm.message import ImageContent, Message, TextContent

    msgs = [
        Message(
            role="user",
            content=[
                TextContent(text="Analyze this image and get weather data:"),
                ImageContent(image_urls=["data:image/png;base64,weather_map"]),
            ],
            vision_enabled=True,
        ).to_llm_dict(),
        Message(
            role="assistant",
            content=[TextContent(text="I'll analyze the image and get weather data.")],
            tool_calls=[
                ChatCompletionMessageToolCall(
                    id="call_1",
                    type="function",
                    function=Function(
                        name="get_weather", arguments='{"location":"NYC"}'
                    ),
                )
            ],
        ).to_llm_dict(),
        Message(
            role="tool",
            content=[TextContent(text="Sunny, 75°F")],
            tool_call_id="call_1",
        ).to_llm_dict(),
    ]
    items = messages_to_responses_items(msgs)
    items = cast(list[dict[str, Any]], items)

    # Should produce: user text, image, assistant text, function_call, function_output
    assert len(items) == 5
    assert items[0] == {
        "role": "user",
        "content": "Analyze this image and get weather data:",
    }
    assert items[1] == {
        "type": "input_image",
        "image_url": "data:image/png;base64,weather_map",
    }
    assert items[2] == {
        "role": "assistant",
        "content": "I'll analyze the image and get weather data.",
    }
    assert items[3]["type"] == "function_call"
    assert items[4]["type"] == "function_call_output"


def test_responses_to_completion_format_basic():
    """Test basic conversion from responses format to completion format.

    Use real OpenAI Responses item types for message and reasoning.
    """

    from openai.types.responses.response_output_message import ResponseOutputMessage
    from openai.types.responses.response_output_text import ResponseOutputText
    from openai.types.responses.response_reasoning_item import (
        Content,
        ResponseReasoningItem,
    )

    # Minimal usage mock (we only read token counts)
    class MockUsage:
        def __init__(self, input_tokens=10, output_tokens=20, total_tokens=30):
            self.input_tokens = input_tokens
            self.output_tokens = output_tokens
            self.total_tokens = total_tokens
            self.output_tokens_details = None

    class MockResponse:
        def __init__(self):
            self.id = "resp_123"
            self.created_at = 1234567890
            self.model = "o1-preview"
            # Message with a single text segment
            seg = ResponseOutputText(
                type="output_text",
                text="Hello, how can I help you?",
                annotations=[],
                logprobs=None,
            )
            msg = ResponseOutputMessage(
                id="msg_1",
                role="assistant",
                status="completed",
                type="message",
                content=[seg],
            )
            # Reasoning content as explicit content segments
            r_content = [
                Content(
                    text="The user is greeting me, I should respond politely.",
                    type="reasoning_text",
                )
            ]
            reasoning = ResponseReasoningItem(
                id="r_1",
                type="reasoning",
                status="completed",
                summary=[],
                content=r_content,
            )
            self.output = [msg, reasoning]
            self.usage = MockUsage()

    mock_response = MockResponse()
    result = responses_to_completion_format(cast(Response, mock_response))

    assert isinstance(result, ModelResponse)
    assert result.id == "resp_123"
    assert result.model == "o1-preview"
    assert result.created == 1234567890
    assert len(result.choices) == 1

    choice = result.choices[0]
    assert choice.index == 0
    assert choice.finish_reason == "stop"
    assert choice.message.role == "assistant"  # type: ignore[attr-defined]
    assert choice.message.content == "Hello, how can I help you?"  # type: ignore[attr-defined]
    assert hasattr(choice.message, "reasoning_content")  # type: ignore[attr-defined]
    assert (
        choice.message.reasoning_content  # type: ignore[attr-defined]
        == "The user is greeting me, I should respond politely."
    )

    assert result.usage.prompt_tokens == 10  # type: ignore[attr-defined]
    assert result.usage.completion_tokens == 20  # type: ignore[attr-defined]
    assert result.usage.total_tokens == 30  # type: ignore[attr-defined]


def test_responses_to_completion_format_no_reasoning():
    """Test conversion without reasoning content using real message segment types."""

    from openai.types.responses.response_output_message import ResponseOutputMessage
    from openai.types.responses.response_output_text import ResponseOutputText

    class MockResponse:
        def __init__(self):
            self.id = "resp_456"
            self.created_at = 1234567891
            self.model = "gpt-4o"
            seg = ResponseOutputText(
                type="output_text",
                text="Just a regular response.",
                annotations=[],
                logprobs=None,
            )
            msg = ResponseOutputMessage(
                id="msg_2",
                role="assistant",
                status="completed",
                type="message",
                content=[seg],
            )
            self.output = [msg]

    mock_response = MockResponse()
    result = responses_to_completion_format(cast(Response, mock_response))

    assert isinstance(result, ModelResponse)
    assert result.choices[0].message.content == "Just a regular response."  # type: ignore[attr-defined]
    assert not hasattr(result.choices[0].message, "reasoning_content")  # type: ignore[attr-defined]


def test_responses_to_completion_format_empty_output():
    """Test conversion with empty output."""

    class MockResponse:
        def __init__(self):
            self.id = "resp_789"
            self.created_at = 1234567892
            self.model = "o1-mini"
            self.output = []

    mock_response = MockResponse()
    result = responses_to_completion_format(cast(Response, mock_response))

    assert isinstance(result, ModelResponse)
    assert result.choices[0].message.content == ""  # type: ignore[attr-defined]
    assert not hasattr(result.choices[0].message, "reasoning_content")  # type: ignore[attr-defined]
