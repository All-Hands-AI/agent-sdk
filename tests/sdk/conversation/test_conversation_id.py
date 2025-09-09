import uuid
from unittest.mock import MagicMock

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.conversation.types import ConversationCallbackType
from openhands.sdk.event.llm_convertible import SystemPromptEvent
from openhands.sdk.llm import TextContent


class DummyAgent(AgentBase):
    def __init__(self):
        super().__init__(llm=MagicMock(name="LLM"), tools=[])
        self.prompt_manager = MagicMock()

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
        pass


def test_conversation_has_unique_id():
    """Test that each conversation gets a unique UUID."""
    agent = DummyAgent()
    conversation = Conversation(agent=agent)

    # Check that id exists and is a string
    assert hasattr(conversation, "id")
    assert isinstance(conversation.id, str)

    # Check that it's a valid UUID format
    try:
        uuid.UUID(conversation.id)
    except ValueError:
        assert False, f"Conversation ID '{conversation.id}' is not a valid UUID"


def test_conversation_ids_are_unique():
    """Test that different conversations get different IDs."""
    agent1 = DummyAgent()
    agent2 = DummyAgent()

    conversation1 = Conversation(agent=agent1)
    conversation2 = Conversation(agent=agent2)

    # Check that the IDs are different
    assert conversation1.id != conversation2.id

    # Check that both are valid UUIDs
    try:
        uuid.UUID(conversation1.id)
        uuid.UUID(conversation2.id)
    except ValueError:
        assert False, "One or both conversation IDs are not valid UUIDs"


def test_conversation_id_persists():
    """Test that the conversation ID doesn't change during the conversation lifecycle."""  # noqa: E501
    agent = DummyAgent()
    conversation = Conversation(agent=agent)

    original_id = conversation.id

    # Perform some operations that might affect the conversation
    conversation.set_confirmation_mode(True)
    conversation.set_confirmation_mode(False)

    # Check that the ID hasn't changed
    assert conversation.id == original_id
