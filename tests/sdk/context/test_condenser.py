from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.context.condenser.no_op_condenser import NoOpCondenser
from openhands.sdk.context.view import View
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.event import Event
from openhands.sdk.event.llm_convertible import MessageEvent
from openhands.sdk.io.memory import InMemoryFileStore
from openhands.sdk.llm import LLM, Message, TextContent


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
    # Create a real agent for testing
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    agent = Agent(llm=llm, tools=[])

    # Use create method with InMemoryFileStore to properly initialize the state
    state = ConversationState.create(
        id="test-id",
        agent=agent,
        file_store=InMemoryFileStore(),
    )

    # Add events to the state
    for event in events:
        state.events.append(event)

    condenser = NoOpCondenser()
    view = View.from_events(state.events)

    condensation_result = condenser.condense(view)
    assert isinstance(condensation_result, View)
    assert condensation_result.events == events
