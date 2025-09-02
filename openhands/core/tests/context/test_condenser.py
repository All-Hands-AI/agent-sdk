from openhands.core.context.condenser.no_op_condenser import NoOpCondenser
from openhands.core.context.view import View
from openhands.core.conversation.state import ConversationState
from openhands.core.event import EventType
from openhands.core.event.llm_convertible import MessageEvent
from openhands.core.llm import Message, TextContent


def message_event(content: str) -> MessageEvent:
    return MessageEvent(llm_message=Message(role="user", content=[TextContent(text=content)]), source="user")


def test_noop_condenser() -> None:
    """Test that NoOpCondensers preserve their input events."""
    events: list[EventType] = [
        message_event("Event 1"),
        message_event("Event 2"),
        message_event("Event 3"),
    ]
    state = ConversationState(events=events)

    condenser = NoOpCondenser()
    view = View.from_events(state.events)

    condensation_result = condenser.condense(view)
    assert isinstance(condensation_result, View)
    assert condensation_result.events == events
