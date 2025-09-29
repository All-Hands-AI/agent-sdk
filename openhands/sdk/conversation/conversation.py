from collections.abc import Iterable
from typing import TYPE_CHECKING, Self, overload

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation.base import BaseConversation
from openhands.sdk.conversation.types import ConversationCallbackType, ConversationID
from openhands.sdk.logger import get_logger


if TYPE_CHECKING:
    from openhands.sdk.conversation.impl.local_conversation import LocalConversation
    from openhands.sdk.conversation.impl.remote_conversation import RemoteConversation

logger = get_logger(__name__)


def compose_callbacks(
    callbacks: Iterable[ConversationCallbackType],
) -> ConversationCallbackType:
    def composed(event) -> None:
        for cb in callbacks:
            if cb:
                cb(event)

    return composed


class Conversation:
    """Factory entrypoint that returns a LocalConversation or RemoteConversation.

    Usage:
        - Conversation(agent=...) -> LocalConversation
        - Conversation(agent=..., host="http://...") -> RemoteConversation
    """

    @overload
    def __new__(
        cls: type[Self],
        agent: AgentBase,
        *,
        working_dir: str = "workspace/project",
        persistence_dir: str | None = None,
        conversation_id: ConversationID | None = None,
        callbacks: list[ConversationCallbackType] | None = None,
        max_iteration_per_run: int = 500,
        stuck_detection: bool = True,
        visualize: bool = True,
    ) -> "LocalConversation": ...

    @overload
    def __new__(
        cls: type[Self],
        agent: AgentBase,
        *,
        host: str,
        working_dir: str = "workspace/project",
        api_key: str | None = None,
        conversation_id: ConversationID | None = None,
        callbacks: list[ConversationCallbackType] | None = None,
        max_iteration_per_run: int = 500,
        stuck_detection: bool = True,
        visualize: bool = True,
    ) -> "RemoteConversation": ...

    def __new__(
        cls: type[Self],
        agent: AgentBase,
        *,
        host: str | None = None,
        working_dir: str = "workspace/project",
        persistence_dir: str | None = None,
        api_key: str | None = None,
        conversation_id: ConversationID | None = None,
        callbacks: list[ConversationCallbackType] | None = None,
        max_iteration_per_run: int = 500,
        stuck_detection: bool = True,
        visualize: bool = True,
    ) -> BaseConversation:
        from openhands.sdk.conversation.impl.local_conversation import LocalConversation
        from openhands.sdk.conversation.impl.remote_conversation import (
            RemoteConversation,
        )

        if host:
            # For RemoteConversation, persistence_dir should not be used
            # Only check if it was explicitly set to something other than the default
            if persistence_dir is not None:
                raise ValueError(
                    "persistence_dir should not be set when using RemoteConversation"
                )
            return RemoteConversation(
                agent=agent,
                host=host,
                api_key=api_key,
                conversation_id=conversation_id,
                callbacks=callbacks,
                max_iteration_per_run=max_iteration_per_run,
                stuck_detection=stuck_detection,
                visualize=visualize,
                working_dir=working_dir,
            )

        return LocalConversation(
            agent=agent,
            conversation_id=conversation_id,
            callbacks=callbacks,
            max_iteration_per_run=max_iteration_per_run,
            stuck_detection=stuck_detection,
            visualize=visualize,
            working_dir=working_dir,
            persistence_dir=persistence_dir,
        )
