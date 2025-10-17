"""Test that thinking blocks are preserved when events are filtered/condensed."""

from collections.abc import Sequence

from openhands.sdk.context.view import View
from openhands.sdk.event import ActionEvent, Condensation, ObservationEvent
from openhands.sdk.event.base import LLMConvertibleEvent
from openhands.sdk.llm.message import (
    ImageContent,
    MessageToolCall,
    RedactedThinkingBlock,
    TextContent,
    ThinkingBlock,
)
from openhands.sdk.tool import Observation


class MockObservation(Observation):
    """Mock observation for testing."""

    result: str

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        return [TextContent(text=self.result)]


def test_thinking_blocks_preserved_after_condensation():
    """Test that thinking blocks survive when early events are condensed."""
    # Simulate 4 ActionEvents from same LLM response with parallel tool calls
    # All should have the same thinking_blocks (as per the fix)
    thinking_blocks: list[ThinkingBlock | RedactedThinkingBlock] = [
        ThinkingBlock(
            type="thinking",
            thinking="Let me analyze this...",
            signature="mock_signature_123",
        )
    ]

    e44 = ActionEvent(
        id="44",
        source="agent",
        tool_name="test_tool_1",
        tool_call=MessageToolCall(
            id="call_1", name="test_tool_1", arguments="{}", origin="completion"
        ),
        tool_call_id="call_1",
        llm_response_id="response_123",
        thinking_blocks=thinking_blocks,
        reasoning_content="reasoning here",
        thought=[],
        action=None,
    )

    e45 = ActionEvent(
        id="45",
        source="agent",
        tool_name="test_tool_2",
        tool_call=MessageToolCall(
            id="call_2", name="test_tool_2", arguments="{}", origin="completion"
        ),
        tool_call_id="call_2",
        llm_response_id="response_123",
        thinking_blocks=thinking_blocks,  # Now all events have thinking_blocks
        reasoning_content="reasoning here",
        thought=[],
        action=None,
    )

    e46 = ActionEvent(
        id="46",
        source="agent",
        tool_name="test_tool_3",
        tool_call=MessageToolCall(
            id="call_3", name="test_tool_3", arguments="{}", origin="completion"
        ),
        tool_call_id="call_3",
        llm_response_id="response_123",
        thinking_blocks=thinking_blocks,  # Now all events have thinking_blocks
        reasoning_content="reasoning here",
        thought=[],
        action=None,
    )

    e47 = ActionEvent(
        id="47",
        source="agent",
        tool_name="test_tool_4",
        tool_call=MessageToolCall(
            id="call_4", name="test_tool_4", arguments="{}", origin="completion"
        ),
        tool_call_id="call_4",
        llm_response_id="response_123",
        thinking_blocks=thinking_blocks,  # Now all events have thinking_blocks
        reasoning_content="reasoning here",
        thought=[],
        action=None,
    )

    # Add ObservationEvents for each ActionEvent so they're not filtered out
    obs44 = ObservationEvent(
        id="48",
        source="environment",
        observation=MockObservation(result="Result 1"),
        action_id="44",
        tool_name="test_tool_1",
        tool_call_id="call_1",
    )

    obs45 = ObservationEvent(
        id="49",
        source="environment",
        observation=MockObservation(result="Result 2"),
        action_id="45",
        tool_name="test_tool_2",
        tool_call_id="call_2",
    )

    obs46 = ObservationEvent(
        id="50",
        source="environment",
        observation=MockObservation(result="Result 3"),
        action_id="46",
        tool_name="test_tool_3",
        tool_call_id="call_3",
    )

    obs47 = ObservationEvent(
        id="51",
        source="environment",
        observation=MockObservation(result="Result 4"),
        action_id="47",
        tool_name="test_tool_4",
        tool_call_id="call_4",
    )

    # Simulate condenser removing events 44-46, keeping only 47 and obs47
    condensation = Condensation(
        id="100",
        forgotten_event_ids=["44", "45", "46", "48", "49", "50"],
        summary=None,
        summary_offset=None,
    )

    all_events = [e44, obs44, e45, obs45, e46, obs46, e47, obs47, condensation]

    # Create view which respects condensation
    view = View.from_events(all_events)

    # View should contain e47 and obs47
    assert len(view.events) == 2
    assert view.events[0].id == "47"
    assert view.events[1].id == "51"

    # Convert events to messages
    messages = LLMConvertibleEvent.events_to_messages(view.events)

    # Should have 2 messages: 1 assistant + 1 tool response
    assert len(messages) == 2
    assert messages[0].role == "assistant"
    assert messages[1].role == "tool"

    # The assistant message should have thinking_blocks (not lost during condensation)
    assert len(messages[0].thinking_blocks) == 1
    assert isinstance(messages[0].thinking_blocks[0], ThinkingBlock)
    assert messages[0].thinking_blocks[0].thinking == "Let me analyze this..."

    # The assistant message should have the tool call
    assert messages[0].tool_calls and len(messages[0].tool_calls) == 1
    assert messages[0].tool_calls[0].id == "call_4"


def test_thinking_blocks_not_duplicated_when_combining():
    """Test thinking blocks not duplicated when combining multiple ActionEvents."""
    thinking_blocks: list[ThinkingBlock | RedactedThinkingBlock] = [
        ThinkingBlock(
            type="thinking", thinking="Thinking content", signature="mock_signature_456"
        )
    ]

    # Create 3 ActionEvents with same llm_response_id and same thinking_blocks
    events: list[LLMConvertibleEvent] = [
        ActionEvent(
            id=str(i),
            source="agent",
            tool_name=f"tool_{i}",
            tool_call=MessageToolCall(
                id=f"call_{i}",
                name=f"tool_{i}",
                arguments="{}",
                origin="completion",
            ),
            tool_call_id=f"call_{i}",
            llm_response_id="response_xyz",
            thinking_blocks=thinking_blocks,
            reasoning_content="reasoning",
            thought=[] if i > 0 else [],
            action=None,
        )
        for i in range(3)
    ]

    # Convert to messages
    messages = LLMConvertibleEvent.events_to_messages(events)

    # Should combine into 1 message
    assert len(messages) == 1

    # Should have thinking_blocks (not duplicated)
    assert len(messages[0].thinking_blocks) == 1
    assert isinstance(messages[0].thinking_blocks[0], ThinkingBlock)
    assert messages[0].thinking_blocks[0].thinking == "Thinking content"

    # Should have all 3 tool calls
    assert messages[0].tool_calls and len(messages[0].tool_calls) == 3
