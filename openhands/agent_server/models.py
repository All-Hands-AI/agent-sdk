from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from openhands.agent_server.utils import utc_now
from openhands.sdk import (
    AgentSpec,
    EventBase,
    ImageContent,
    Message,
    TextContent,
)
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.llm.utils.metrics import MetricsSnapshot
from openhands.sdk.utils.models import OpenHandsModel


class ConversationSortOrder(str, Enum):
    """Enum for conversation sorting options."""

    CREATED_AT = "CREATED_AT"
    UPDATED_AT = "UPDATED_AT"
    CREATED_AT_DESC = "CREATED_AT_DESC"
    UPDATED_AT_DESC = "UPDATED_AT_DESC"


class EventSortOrder(str, Enum):
    """Enum for event sorting options."""

    TIMESTAMP = "TIMESTAMP"
    TIMESTAMP_DESC = "TIMESTAMP_DESC"


class SendMessageRequest(BaseModel):
    """Payload to send a message to the agent.

    This is a simplified version of openhands.sdk.Message.
    """

    role: Literal["user", "system", "assistant", "tool"] = "user"
    content: list[TextContent | ImageContent] = Field(default_factory=list)
    run: bool = Field(
        default=True,
        description="If true, immediately run the agent after sending the message.",
    )

    def create_message(self) -> Message:
        message = Message(role=self.role, content=self.content)
        return message


class StartConversationRequest(AgentSpec):
    """Payload to create a new conversation.

    It inherits from AgentSpec which contains everything needed
    to start a new conversation.
    """

    # These are two conversation specific fields
    confirmation_mode: bool = Field(
        default=False,
        description="If true, the agent will enter confirmation mode, "
        "requiring user approval for actions.",
    )
    initial_message: SendMessageRequest | None = Field(
        default=None, description="Initial message to pass to the LLM"
    )
    max_iterations: int = Field(
        default=500,
        description="If set, the max number of iterations the agent will run "
        "before stopping. This is useful to prevent infinite loops.",
    )


class StoredConversation(StartConversationRequest):
    """Stored details about a conversation"""

    id: UUID
    metrics: MetricsSnapshot | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ConversationInfo(StoredConversation):
    """Information about a conversation running locally without a Runtime sandbox."""

    status: AgentExecutionStatus = AgentExecutionStatus.IDLE


class ConversationPage(BaseModel):
    items: list[ConversationInfo]
    next_page_id: str | None = None


class ConversationResponse(BaseModel):
    conversation_id: str
    state: AgentExecutionStatus


class ConfirmationResponseRequest(BaseModel):
    """Payload to accept or reject a pending action."""

    accept: bool
    reason: str = "User rejected the action."


class Success(BaseModel):
    success: bool = True


class EventPage(OpenHandsModel):
    items: list[EventBase]
    next_page_id: str | None = None
