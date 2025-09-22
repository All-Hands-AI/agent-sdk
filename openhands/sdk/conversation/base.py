from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol

from openhands.sdk.conversation.secrets_manager import SecretValue
from openhands.sdk.conversation.types import ConversationID
from openhands.sdk.llm.message import Message
from openhands.sdk.security.confirmation_policy import ConfirmationPolicyBase
from openhands.sdk.utils.protocol import ListLike


if TYPE_CHECKING:
    from openhands.sdk.event.base import EventBase


class ConversationStateProtocol(Protocol):
    """Protocol defining the interface for conversation state objects."""

    @property
    def id(self) -> ConversationID:
        """The conversation ID."""
        ...

    @property
    def events(self) -> ListLike["EventBase"]:
        """Access to the events list."""
        ...


class BaseConversation(ABC):
    @property
    @abstractmethod
    def id(self) -> ConversationID: ...

    @property
    @abstractmethod
    def state(self) -> ConversationStateProtocol: ...

    @abstractmethod
    def send_message(self, message: str | Message) -> None: ...

    @abstractmethod
    def run(self) -> None: ...

    @abstractmethod
    def set_confirmation_policy(self, policy: ConfirmationPolicyBase) -> None: ...

    @abstractmethod
    def reject_pending_actions(
        self, reason: str = "User rejected the action"
    ) -> None: ...

    @abstractmethod
    def pause(self) -> None: ...

    @abstractmethod
    def update_secrets(self, secrets: dict[str, SecretValue]) -> None: ...

    @abstractmethod
    def close(self) -> None: ...
