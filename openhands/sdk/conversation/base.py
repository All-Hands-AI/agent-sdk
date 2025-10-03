from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from openhands.sdk.conversation.conversation_stats import ConversationStats
from openhands.sdk.conversation.events_list_base import EventsListBase
from openhands.sdk.conversation.secrets_manager import SecretValue
from openhands.sdk.conversation.types import ConversationCallbackType, ConversationID
from openhands.sdk.llm.message import Message
from openhands.sdk.security.confirmation_policy import (
    ConfirmationPolicyBase,
    NeverConfirm,
)
from openhands.sdk.workspace.base import BaseWorkspace


if TYPE_CHECKING:
    from openhands.sdk.agent.base import AgentBase
    from openhands.sdk.conversation.state import AgentExecutionStatus


class ConversationStateProtocol(Protocol):
    """Protocol defining the interface for conversation state objects."""

    @property
    def id(self) -> ConversationID:
        """The conversation ID."""
        ...

    @property
    def events(self) -> EventsListBase:
        """Access to the events list."""
        ...

    @property
    def agent_status(self) -> "AgentExecutionStatus":
        """The current agent execution status."""
        ...

    @property
    def confirmation_policy(self) -> ConfirmationPolicyBase:
        """The confirmation policy."""
        ...

    @property
    def activated_knowledge_microagents(self) -> list[str]:
        """List of activated knowledge microagents."""
        ...

    @property
    def workspace(self) -> BaseWorkspace:
        """The workspace for agent operations and tool execution."""
        ...

    @property
    def persistence_dir(self) -> str | None:
        """The persistence directory from the FileStore.

        If None, it means the conversation is not being persisted.
        """
        ...

    @property
    def agent(self) -> "AgentBase":
        """The agent running in the conversation."""
        ...


class BaseConversation(ABC):
    @property
    @abstractmethod
    def id(self) -> ConversationID: ...

    @property
    @abstractmethod
    def state(self) -> ConversationStateProtocol: ...

    @property
    @abstractmethod
    def conversation_stats(self) -> ConversationStats: ...

    @abstractmethod
    def send_message(self, message: str | Message) -> None: ...

    @abstractmethod
    def run(self) -> None: ...

    @abstractmethod
    def set_confirmation_policy(self, policy: ConfirmationPolicyBase) -> None: ...

    @property
    def confirmation_policy_active(self) -> bool:
        return not isinstance(self.state.confirmation_policy, NeverConfirm)

    @abstractmethod
    def reject_pending_actions(
        self, reason: str = "User rejected the action"
    ) -> None: ...

    @abstractmethod
    def pause(self) -> None: ...

    @abstractmethod
    def update_secrets(self, secrets: Mapping[str, SecretValue]) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @staticmethod
    def get_persistence_dir(
        persistence_base_dir: str, conversation_id: ConversationID
    ) -> str:
        """Get the persistence directory for the conversation."""
        return str(Path(persistence_base_dir) / str(conversation_id))

    @staticmethod
    def compose_callbacks(
        callbacks: Iterable[ConversationCallbackType],
    ) -> ConversationCallbackType:
        """Compose multiple callbacks into a single callback function.

        Args:
            callbacks: An iterable of callback functions

        Returns:
            A single callback function that calls all provided callbacks
        """

        def composed(event) -> None:
            for cb in callbacks:
                if cb:
                    cb(event)

        return composed
