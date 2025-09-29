"""Base state class for conversation state management."""

from enum import Enum
from uuid import UUID

from pydantic import Field

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation.conversation_stats import ConversationStats
from openhands.sdk.security.confirmation_policy import (
    ConfirmationPolicyBase,
    NeverConfirm,
)
from openhands.sdk.utils.models import OpenHandsModel


ConversationID = UUID


class AgentExecutionStatus(str, Enum):
    """Enum representing the current execution state of the agent."""

    IDLE = "idle"  # Agent is ready to receive tasks
    RUNNING = "running"  # Agent is actively processing
    PAUSED = "paused"  # Agent execution is paused by user
    WAITING_FOR_CONFIRMATION = (
        "waiting_for_confirmation"  # Agent is waiting for user confirmation
    )
    FINISHED = "finished"  # Agent has completed the current task
    ERROR = "error"  # Agent encountered an error (optional for future use)
    STUCK = "stuck"  # Agent is stuck in a loop or unable to proceed


class ConversationBaseState(OpenHandsModel):
    """Base class containing common conversation state fields.

    This class defines the core state fields that are shared between
    ConversationState and ConversationStateUpdateEvent. The base class uses
    the same strict types as ConversationState, and ConversationStateUpdateEvent
    will override these fields with serialized types for websocket transmission.

    Note: The 'id' field is intentionally excluded from this base class because
    ConversationState uses ConversationID (UUID) while ConversationStateUpdateEvent
    uses EventID (string), and they have different semantics.
    """

    agent: AgentBase = Field(
        ...,
        description=(
            "The agent running in the conversation. "
            "This is persisted to allow resuming conversations and "
            "check agent configuration to handle e.g., tool changes, "
            "LLM changes, etc."
        ),
    )
    working_dir: str = Field(
        default="workspace/project",
        description="Working directory for agent operations and tool execution",
    )
    persistence_dir: str | None = Field(
        default="workspace/conversations",
        description="Directory for persisting conversation state and events. "
        "If None, conversation will not be persisted.",
    )
    max_iterations: int = Field(
        default=500,
        gt=0,
        description="Maximum number of iterations the agent can "
        "perform in a single run.",
    )
    stuck_detection: bool = Field(
        default=True,
        description="Whether to enable stuck detection for the agent.",
    )
    agent_status: AgentExecutionStatus = Field(default=AgentExecutionStatus.IDLE)
    confirmation_policy: ConfirmationPolicyBase = NeverConfirm()
    activated_knowledge_microagents: list[str] = Field(
        default_factory=list,
        description="List of activated knowledge microagents name",
    )
    stats: ConversationStats = Field(
        default_factory=ConversationStats,
        description="Conversation statistics for tracking LLM metrics",
    )
