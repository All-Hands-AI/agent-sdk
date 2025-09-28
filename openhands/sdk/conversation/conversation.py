from collections.abc import Iterable
from typing import TYPE_CHECKING, Self, overload

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation.base import BaseConversation
from openhands.sdk.conversation.types import ConversationCallbackType, ConversationID
from openhands.sdk.io import FileStore
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
        persist_filestore: FileStore | None = None,
        conversation_id: ConversationID | None = None,
        callbacks: list[ConversationCallbackType] | None = None,
        max_iteration_per_run: int = 500,
        stuck_detection: bool = True,
        visualize: bool = True,
        working_dir: str | None = None,
        persistence_dir: str | None = None,
    ) -> "LocalConversation": ...

    @overload
    def __new__(
        cls: type[Self],
        agent: AgentBase,
        *,
        host: str,
        api_key: str | None = None,
        conversation_id: ConversationID | None = None,
        callbacks: list[ConversationCallbackType] | None = None,
        max_iteration_per_run: int = 500,
        stuck_detection: bool = True,
        visualize: bool = True,
        working_dir: str | None = None,
        persistence_dir: str | None = None,
    ) -> "RemoteConversation": ...

    def __new__(
        cls: type[Self],
        agent: AgentBase,
        *,
        persist_filestore: FileStore | None = None,
        host: str | None = None,
        api_key: str | None = None,
        conversation_id: ConversationID | None = None,
        callbacks: list[ConversationCallbackType] | None = None,
        max_iteration_per_run: int = 500,
        stuck_detection: bool = True,
        visualize: bool = True,
        working_dir: str | None = None,
        persistence_dir: str | None = None,
    ) -> BaseConversation:
        from openhands.sdk.conversation.impl.local_conversation import LocalConversation
        from openhands.sdk.conversation.impl.remote_conversation import (
            RemoteConversation,
        )

        if host:
            return RemoteConversation(
                agent=agent,
                host=host,
                api_key=api_key,
                conversation_id=conversation_id,
                callbacks=callbacks,
                max_iteration_per_run=max_iteration_per_run,
                stuck_detection=stuck_detection,
                visualize=visualize,
            )

        # Set default directories if not provided
        import os

        if working_dir is None:
            working_dir = os.getcwd()

        if persistence_dir is None:
            persistence_dir = os.path.join(working_dir, ".openhands")

        # Handle persistence_dir parameter by creating LocalFileStore if needed
        if persistence_dir and persist_filestore is None:
            from openhands.sdk.io.local import LocalFileStore

            persist_filestore = LocalFileStore(persistence_dir)

        return LocalConversation(
            agent=agent,
            persist_filestore=persist_filestore,
            conversation_id=conversation_id,
            callbacks=callbacks,
            max_iteration_per_run=max_iteration_per_run,
            stuck_detection=stuck_detection,
            visualize=visualize,
            working_dir=working_dir,
        )
