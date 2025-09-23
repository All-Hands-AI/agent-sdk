from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Discriminator, Field, Tag

from openhands.agent_server.utils import utc_now
from openhands.sdk import AgentBase, EventBase, ImageContent, Message, TextContent
from openhands.sdk.conversation.state import AgentExecutionStatus, ConversationState
from openhands.sdk.event.llm_convertible.action import ActionEvent
from openhands.sdk.event.llm_convertible.observation import ObservationEvent
from openhands.sdk.llm.utils.metrics import MetricsSnapshot
from openhands.sdk.security.confirmation_policy import (
    ConfirmationPolicyBase,
    NeverConfirm,
)
from openhands.sdk.utils.models import OpenHandsModel, kind_of


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

    def create_message(self) -> Message:
        message = Message(role=self.role, content=self.content)
        return message


class StartConversationRequest(BaseModel):
    """Payload to create a new conversation.

    Contains an Agent configuration along with conversation-specific options.
    """

    agent: AgentBase
    confirmation_policy: ConfirmationPolicyBase = Field(
        default=NeverConfirm(),
        description="Controls when the conversation will prompt the user before "
        "continuing. Defaults to never.",
    )
    initial_message: SendMessageRequest | None = Field(
        default=None, description="Initial message to pass to the LLM"
    )
    max_iterations: int = Field(
        default=500,
        ge=1,
        description="If set, the max number of iterations the agent will run "
        "before stopping. This is useful to prevent infinite loops.",
    )
    stuck_detection: bool = Field(
        default=True,
        description="If true, the conversation will use stuck detection to "
        "prevent infinite loops.",
    )


class StoredConversation(StartConversationRequest):
    """Stored details about a conversation"""

    id: UUID
    metrics: MetricsSnapshot | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ConversationInfo(ConversationState):
    """Information about a conversation running locally without a Runtime sandbox."""

    # ConversationState already includes id and agent
    # Add additional metadata fields

    metrics: MetricsSnapshot | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


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


class UpdateSecretsRequest(BaseModel):
    """Payload to update secrets in a conversation."""

    secrets: dict[str, str] = Field(
        description="Dictionary mapping secret keys to values"
    )


class SetConfirmationPolicyRequest(BaseModel):
    """Payload to set confirmation policy for a conversation."""

    policy: ConfirmationPolicyBase = Field(description="The confirmation policy to set")


ToolEvent = Annotated[
    Union[
        Annotated[ActionEvent, Tag("ActionEvent")],
        Annotated[ObservationEvent, Tag("ObservationEvent")],
    ],
    Discriminator(kind_of),
]


class ToolEventPage(BaseModel):
    items: list[ToolEvent]
    next_page_id: str | None = None
