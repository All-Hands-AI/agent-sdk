"""Events related to conversation state updates."""

import uuid
from typing import Any

from pydantic import Field

from openhands.sdk.conversation.base_state import ConversationBaseState
from openhands.sdk.event.base import EventBase
from openhands.sdk.event.types import EventID, SourceType


class ConversationStateUpdateEvent(EventBase, ConversationBaseState):
    """Event that contains conversation state updates.

    This event is sent via websocket whenever the conversation state changes,
    allowing remote clients to stay in sync without making REST API calls.
    """

    source: SourceType = "environment"

    # Conversation identification (using EventID for websocket compatibility)
    id: EventID = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Conversation ID as string",
    )

    # Override base fields with serialized types for websocket transmission
    agent_status: str
    confirmation_policy: dict[str, Any]
    agent: dict[str, Any]
    conversation_stats: dict[str, Any]

    def __str__(self) -> str:
        return f"ConversationStateUpdate(agent_status={self.agent_status})"
