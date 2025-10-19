from openhands.sdk.context.condenser.no_op_condenser import NoOpCondenser
from openhands.sdk.context.view import View
from openhands.sdk.event.base import Event
from openhands.sdk.event.llm_convertible import MessageEvent
from openhands.sdk.llm import Message, TextContent


def message_event(content: str) -> MessageEvent:
    return MessageEvent(
        llm_message=Message(role="user", content=[TextContent(text=content)]),
        source="user",
    )


def test_noop_condenser() -> None:
    """Test that NoOpCondensers preserve their input events."""
    events: list[Event] = [
        message_event("Event 1"),
        message_event("Event 2"),
        message_event("Event 3"),
    ]

    condenser = NoOpCondenser()
    view = View.from_events(events)

    condensation_result = condenser.condense(view)
    assert isinstance(condensation_result, View)
    assert condensation_result.events == events
