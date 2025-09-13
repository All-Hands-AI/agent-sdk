"""Tests for responses converter utilities."""

from typing import cast

from litellm.types.llms.openai import ResponsesAPIResponse as Response
from litellm.types.utils import ModelResponse

from openhands.sdk.llm.utils.responses_converter import (
    messages_to_responses_items,
    responses_to_completion_format,
)


def test_messages_to_responses_input_empty():
    assert messages_to_responses_items([]) == []


def test_messages_to_responses_order_assistant_text_before_function_call():
    msgs = [
        {
            "role": "assistant",
            "content": "thinking...",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {"name": "echo", "arguments": '{"s":"hi"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "hi"},
    ]
    items = messages_to_responses_items(msgs)
    # Expect ordering: assistant text, then function_call, then function_call_output
    assert items[0] == {"role": "assistant", "content": "thinking..."}
    assert items[1]["type"] == "function_call" and items[1]["call_id"] == "call_1"
    assert (
        items[2]["type"] == "function_call_output" and items[2]["call_id"] == "call_1"
    )

    msgs = [
        {
            "role": "assistant",
            "content": "thinking...",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {"name": "echo", "arguments": '{"s":"hi"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "hi"},
    ]
    items = messages_to_responses_items(msgs)
    # Expect ordering: assistant text, then function_call, then function_call_output
    assert items[0] == {"role": "assistant", "content": "thinking..."}
    assert items[1]["type"] == "function_call" and items[1]["call_id"] == "call_1"
    assert (
        items[2]["type"] == "function_call_output" and items[2]["call_id"] == "call_1"
    )


def test_messages_to_responses_input_dict_messages():
    msgs = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "U"},
        {"role": "assistant", "content": "A"},
    ]
    assert messages_to_responses_items(msgs) == [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "U"},
        {"role": "assistant", "content": "A"},
    ]


def test_messages_to_responses_input_with_tool_message():
    msgs = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {"name": "f", "arguments": '{"a":1}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "out"},
    ]
    items = messages_to_responses_items(msgs)
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
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "Hi"}]},
    ]
    assert messages_to_responses_items(msgs) == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]


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
