"""Base state class for conversation state management."""

from typing import Any
from uuid import UUID

from pydantic import Field

from openhands.sdk.utils.models import OpenHandsModel


ConversationID = UUID


class ConversationBaseState(OpenHandsModel):
    """Base class containing common conversation state fields.

    This class defines the core state fields that are shared between
    ConversationState (with rich types) and ConversationStateUpdateEvent
    (with serialized types for websocket transmission).

    Note: The 'id' field is intentionally excluded from this base class because
    ConversationState uses ConversationID (UUID) while ConversationStateUpdateEvent
    uses EventID (string), and they have different semantics.
    """

    # Agent configuration and status
    agent_status: Any = Field(description="Current execution status of the agent")
    confirmation_policy: Any = Field(description="Policy for user confirmations")
    activated_knowledge_microagents: list[str] = Field(
        default_factory=list,
        description="List of activated knowledge microagents name",
    )

    # Agent and statistics (types vary between subclasses)
    agent: Any = Field(description="The agent configuration")
    conversation_stats: Any = Field(description="Conversation statistics")
