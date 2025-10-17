"""
Tests for responses API handling of dangling tool calls.

The OpenAI Responses API requires that every function_call must be followed
by a function_call_output. If we have tool_calls without responses, they should
be filtered out to avoid 400 errors.
"""

from openhands.sdk.llm.llm import LLM
from openhands.sdk.llm.message import Message, MessageToolCall, TextContent


def test_format_messages_filters_dangling_function_calls():
    """Test that dangling function_calls (without outputs) are filtered out."""
    llm = LLM(model="gpt-5-mini")

    messages = [
        Message(role="system", content=[TextContent(text="System message")]),
        Message(role="user", content=[TextContent(text="User message")]),
        Message(
            role="assistant",
            content=[TextContent(text="Calling tool")],
            tool_calls=[
                MessageToolCall(
                    id="call_123", name="tool1", arguments="{}", origin="completion"
                )
            ],
        ),
    ]

    instructions, items = llm.format_messages_for_responses(messages)

    # Should not include the dangling function_call
    function_calls = [item for item in items if item.get("type") == "function_call"]
    assert len(function_calls) == 0, "Dangling function_call should be filtered out"

    # Should still have the user message
    user_messages = [
        item
        for item in items
        if item.get("type") == "message" and item.get("role") == "user"
    ]
    assert len(user_messages) == 1


def test_format_messages_keeps_complete_function_call_cycles():
    """Test that complete function_call/output cycles are kept."""
    llm = LLM(model="gpt-5-mini")

    messages = [
        Message(role="system", content=[TextContent(text="System message")]),
        Message(role="user", content=[TextContent(text="User message")]),
        Message(
            role="assistant",
            content=[TextContent(text="Calling tool")],
            tool_calls=[
                MessageToolCall(
                    id="call_123", name="tool1", arguments="{}", origin="completion"
                )
            ],
        ),
        Message(
            role="tool",
            tool_call_id="call_123",
            name="tool1",
            content=[TextContent(text="Tool result")],
        ),
    ]

    instructions, items = llm.format_messages_for_responses(messages)

    # Should include the function_call since it has an output
    function_calls = [item for item in items if item.get("type") == "function_call"]
    assert len(function_calls) == 1, "Complete function_call should be kept"

    # Should also have the function_call_output
    function_outputs = [
        item for item in items if item.get("type") == "function_call_output"
    ]
    assert len(function_outputs) == 1, "Function output should be present"


def test_format_messages_handles_mixed_complete_and_dangling():
    """Test handling of multiple tool calls.

    Where some are complete and some dangling.
    """
    llm = LLM(model="gpt-5-mini")

    messages = [
        Message(role="system", content=[TextContent(text="System message")]),
        Message(role="user", content=[TextContent(text="First message")]),
        # First tool call - complete
        Message(
            role="assistant",
            content=[TextContent(text="Calling tool A")],
            tool_calls=[
                MessageToolCall(
                    id="call_A", name="toolA", arguments="{}", origin="completion"
                )
            ],
        ),
        Message(
            role="tool",
            tool_call_id="call_A",
            name="toolA",
            content=[TextContent(text="Result A")],
        ),
        Message(role="user", content=[TextContent(text="Second message")]),
        # Second tool call - dangling
        Message(
            role="assistant",
            content=[TextContent(text="Calling tool B")],
            tool_calls=[
                MessageToolCall(
                    id="call_B", name="toolB", arguments="{}", origin="completion"
                )
            ],
        ),
    ]

    instructions, items = llm.format_messages_for_responses(messages)

    # Should only have one function_call (call_A)
    function_calls = [item for item in items if item.get("type") == "function_call"]
    assert len(function_calls) == 1, "Only complete function_call should be kept"

    # Verify it's call_A (with fc_ prefix)
    call_ids = [item.get("call_id") or item.get("id") for item in function_calls]
    assert any("call_A" in str(cid) for cid in call_ids), "Should be call_A"

    # Should only have one function_call_output
    function_outputs = [
        item for item in items if item.get("type") == "function_call_output"
    ]
    assert len(function_outputs) == 1


def test_format_messages_handles_parallel_tool_calls():
    """Test that parallel tool calls (all complete) are all kept."""
    llm = LLM(model="gpt-5-mini")

    messages = [
        Message(role="system", content=[TextContent(text="System message")]),
        Message(role="user", content=[TextContent(text="User message")]),
        # Parallel tool calls
        Message(
            role="assistant",
            content=[TextContent(text="Calling multiple tools")],
            tool_calls=[
                MessageToolCall(
                    id="call_X", name="toolX", arguments="{}", origin="completion"
                ),
                MessageToolCall(
                    id="call_Y", name="toolY", arguments="{}", origin="completion"
                ),
            ],
        ),
        Message(
            role="tool",
            tool_call_id="call_X",
            name="toolX",
            content=[TextContent(text="Result X")],
        ),
        Message(
            role="tool",
            tool_call_id="call_Y",
            name="toolY",
            content=[TextContent(text="Result Y")],
        ),
    ]

    instructions, items = llm.format_messages_for_responses(messages)

    # Should have both function_calls
    function_calls = [item for item in items if item.get("type") == "function_call"]
    assert len(function_calls) == 2, (
        "All complete parallel function_calls should be kept"
    )

    # Should have both function_call_outputs
    function_outputs = [
        item for item in items if item.get("type") == "function_call_output"
    ]
    assert len(function_outputs) == 2


def test_format_messages_handles_responses_origin_tool_calls():
    """Test that tool calls from responses API (origin='responses') are handled."""
    llm = LLM(model="gpt-5-mini")

    messages = [
        Message(role="system", content=[TextContent(text="System message")]),
        Message(role="user", content=[TextContent(text="User message")]),
        Message(
            role="assistant",
            content=[TextContent(text="Calling tool")],
            tool_calls=[
                MessageToolCall(
                    id="fc_call_789",
                    name="tool1",
                    arguments="{}",
                    origin="responses",
                )
            ],
        ),
    ]

    instructions, items = llm.format_messages_for_responses(messages)

    # Should not include the dangling function_call even if it's from responses API
    function_calls = [item for item in items if item.get("type") == "function_call"]
    assert len(function_calls) == 0, "Dangling function_call should be filtered"
