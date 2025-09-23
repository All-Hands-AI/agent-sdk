from typing import Iterable

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation.impl import LocalConversation
from openhands.sdk.conversation.types import ConversationCallbackType, ConversationID
from openhands.sdk.io import FileStore
from openhands.sdk.logger import get_logger


# ConversationType = Union[LocalConversation, RemoteConversation]
ConversationType = LocalConversation  # RemoteConversation is not implemented yet.


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

    def __new__(
        cls,
        agent: AgentBase,
        persist_filestore: FileStore | None = None,
        conversation_id: ConversationID | None = None,
        callbacks: list[ConversationCallbackType] | None = None,
        max_iteration_per_run: int = 500,
        stuck_detection: bool = True,
        visualize: bool = True,
        host: str | None = None,
    ) -> ConversationType:
        if host:
            raise NotImplementedError("RemoteConversation is not implemented yet.")
            # return RemoteConversation(
            #     agent=agent,
            #     host=host,
            #     conversation_id=conversation_id,
            #     callbacks=callbacks,
            #     max_iteration_per_run=max_iteration_per_run,
            #     stuck_detection=stuck_detection,
            # )
        return LocalConversation(
            agent=agent,
            persist_filestore=persist_filestore,
            conversation_id=conversation_id,
            callbacks=callbacks,
            max_iteration_per_run=max_iteration_per_run,
            stuck_detection=stuck_detection,
            visualize=visualize,
        )
