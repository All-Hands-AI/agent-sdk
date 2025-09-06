from typing import Any, List
from unittest.mock import MagicMock

from pydantic import Field, SecretStr

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.conversation.types import ConversationCallbackType
from openhands.sdk.event.llm_convertible import MessageEvent, SystemPromptEvent
from openhands.sdk.llm import LLM, Message, TextContent


class DummyAgent(AgentBase):
    prompt_manager: Any = Field(default_factory=lambda: MagicMock())

    def __init__(self):
        # Use a real LLM instance for testing instead of mocking
        test_llm = LLM(model="gpt-4", api_key=SecretStr("test-key"))
        super().__init__(llm=test_llm, tools=[])

    def init_state(
        self, state: ConversationState, on_event: ConversationCallbackType
    ) -> None:
        event = SystemPromptEvent(
            source="agent", system_prompt=TextContent(text="dummy"), tools=[]
        )
        on_event(event)

    def step(
        self, state: ConversationState, on_event: ConversationCallbackType
    ) -> None:
        on_event(
            MessageEvent(
                source="agent",
                llm_message=Message(role="assistant", content=[TextContent(text="ok")]),
            )
        )


def test_default_callback_appends_on_init():
    agent = DummyAgent()
    events_seen: List[str] = []

    convo = Conversation(agent=agent, callbacks=[lambda e: events_seen.append(e.id)])

    assert len(convo.state.events) == 1
    assert isinstance(convo.state.events[0], SystemPromptEvent)
    assert convo.state.events[0].id in events_seen


def test_send_message_appends_once():
    agent = DummyAgent()
    seen_ids: List[str] = []

    def user_cb(event):
        seen_ids.append(event.id)

    convo = Conversation(agent=agent, callbacks=[user_cb])

    convo.send_message(Message(role="user", content=[TextContent(text="hi")]))

    # Now we should have two events: initial system prompt and the user message
    assert len(convo.state.events) == 2
    assert isinstance(convo.state.events[-1], MessageEvent)

    # Ensure the user message event is appended exactly once in state
    last_id = convo.state.events[-1].id
    assert sum(1 for e in convo.state.events if e.id == last_id) == 1

    # Ensure callback saw both events
    assert set(seen_ids) == {e.id for e in convo.state.events}
