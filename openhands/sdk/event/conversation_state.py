"""Events related to conversation state updates."""

import uuid
from typing import TYPE_CHECKING, Any

from pydantic import Field

from openhands.sdk.event.base import EventBase
from openhands.sdk.event.types import EventID, SourceType


if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState


class ConversationStateUpdateEvent(EventBase):
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

    # Serialized conversation state fields for websocket transmission
    agent_status: str = Field(description="Current execution status of the agent")
    confirmation_policy: dict[str, Any] = Field(
        description="Policy for user confirmations"
    )
    activated_knowledge_microagents: list[str] = Field(
        default_factory=list,
        description="List of activated knowledge microagents name",
    )
    agent: dict[str, Any] = Field(description="The agent configuration")
    conversation_stats: dict[str, Any] = Field(description="Conversation statistics")

    @classmethod
    def from_conversation_state(
        cls, state: "ConversationState", event_id: str | None = None
    ) -> "ConversationStateUpdateEvent":
        """Create a ConversationStateUpdateEvent from a ConversationState.

        This factory method handles the serialization of complex types to
        simple types suitable for websocket transmission.

        Args:
            state: The ConversationState to convert
            event_id: Optional event ID to use. If not provided, uses str(state.id)
        """
        return cls(
            id=event_id or str(state.id),
            agent_status=state.agent_status.value,
            confirmation_policy=state.confirmation_policy.model_dump(),
            activated_knowledge_microagents=state.activated_knowledge_microagents,
            agent=state.agent.model_dump(),
            conversation_stats=state.conversation_stats.model_dump(),
        )

    def __str__(self) -> str:
        return f"ConversationStateUpdate(agent_status={self.agent_status})"
