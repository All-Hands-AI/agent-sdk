"""Events related to conversation state updates."""

import uuid
from typing import TYPE_CHECKING

from pydantic import Field

from openhands.sdk.conversation.state.base import ConversationBaseState
from openhands.sdk.event.base import EventBase
from openhands.sdk.event.types import EventID, SourceType


if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState


class ConversationStateUpdateEvent(EventBase, ConversationBaseState):
    """Event that contains conversation state updates.

    This event is sent via websocket whenever the conversation state changes,
    allowing remote clients to stay in sync without making REST API calls.

    All fields are serialized versions of the corresponding ConversationState fields
    to ensure compatibility with websocket transmission.
    """

    source: SourceType = "environment"

    # Conversation identification (using EventID for websocket compatibility)
    id: EventID = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Conversation ID as string",
    )

    @classmethod
    def from_conversation_state(
        cls, state: "ConversationState"
    ) -> "ConversationStateUpdateEvent":
        """Create a ConversationStateUpdateEvent from a ConversationState.

        This factory method handles the serialization of complex types to
        simple types suitable for websocket transmission.

        Args:
            state: The ConversationState to convert
            event_id: Optional event ID to use. If not provided, uses str(state.id)
        """
        return cls(**state.model_dump())

    def __str__(self) -> str:
        return f"ConversationStateUpdate(agent_status={self.agent_status})"
