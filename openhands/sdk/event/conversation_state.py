"""Events related to conversation state updates."""

from typing import Any

from openhands.sdk.event.base import EventBase
from openhands.sdk.event.types import SourceType


class ConversationStateUpdateEvent(EventBase):
    """Event that contains conversation state updates.

    This event is sent via websocket whenever the conversation state changes,
    allowing remote clients to stay in sync without making REST API calls.
    """

    source: SourceType = "environment"

    # Core state fields that RemoteState needs
    agent_status: str
    confirmation_policy: dict[str, Any]
    activated_knowledge_microagents: list[str]
    agent: dict[str, Any]
    conversation_stats: dict[str, Any]

    def __str__(self) -> str:
        return f"ConversationStateUpdate(agent_status={self.agent_status})"
