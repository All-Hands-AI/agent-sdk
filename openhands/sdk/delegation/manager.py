"""DelegationManager for handling agent delegation and message routing."""

import threading
from typing import TYPE_CHECKING

from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.event import MessageEvent
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.workspace import LocalWorkspace


if TYPE_CHECKING:
    from openhands.sdk.agent.base import AgentBase
    from openhands.sdk.conversation.base import BaseConversation

logger = get_logger(__name__)


class DelegationManager:
    """Manages agent delegation relationships and message routing.

    This class handles:
    - Creating sub-agents and their conversations
    - Tracking parent-child relationships in memory
    - Routing messages between parent and child agents
    - Managing sub-agent lifecycle

    This is implemented as a singleton to avoid needing to pass the instance around.
    """

    _instance: "DelegationManager | None" = None
    _lock = threading.Lock()

    def __new__(cls):
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # Only initialize once
        if self._initialized:
            return
        self._initialized = True

        # Store conversation by id
        self.conversations: dict[str, BaseConversation] = {}
        # Track parent-child relationships (child_id -> parent_id)
        self.child_to_parent: dict[str, str] = {}
        # Track sub-agent threads
        self.sub_agent_threads: dict[str, threading.Thread] = {}
        # Track parent conversation threads (triggered by sub-agent messages)
        self.parent_threads: dict[str, list[threading.Thread]] = {}

    def register_conversation(self, conversation: "BaseConversation") -> None:
        """Register a conversation with the delegation manager.

        This allows the conversation to be looked up by ID when spawning sub-agents.

        Args:
            conversation: The conversation to register
        """
        self.conversations[str(conversation.id)] = conversation
        logger.debug(f"Registered conversation {conversation.id}")

    def get_conversation(self, conversation_id: str) -> "BaseConversation | None":
        """Get a conversation by ID.

        Args:
            conversation_id: The conversation ID to look up

        Returns:
            The conversation object if found, None otherwise
        """
        return self.conversations.get(conversation_id)

    def spawn_sub_agent(
        self,
        parent_conversation: "BaseConversation",
        task: str,
        worker_agent: "AgentBase",
        visualize: bool = False,
    ) -> "BaseConversation":
        """Spawn a sub-agent with a new conversation that runs asynchronously.

        The sub-agent will run in a background thread and send messages back to
        the parent conversation when it completes or needs input.

        Args:
            parent_conversation: The parent conversation
            task: The task description for the sub-agent
            worker_agent: The worker agent to use for the sub-conversation
            visualize: Whether to enable visualization for the sub-agent

        Returns:
            The new sub-conversation
        """
        # We need to create a closure that captures the sub_conversation_id
        # But we need the conversation ID first, so we'll use a placeholder
        # that gets updated after conversation creation
        sub_conversation_id_holder: list[str | None] = [
            None
        ]  # Mutable container for closure

        # Create a callback to route sub-agent messages to parent
        def sub_agent_completion_callback(event):
            """Route sub-agent completion messages to parent."""
            # When sub-agent sends a message, forward it to parent
            if isinstance(event, MessageEvent) and event.source == "agent":
                # Get the message content
                if hasattr(event, "llm_message") and event.llm_message:
                    message_text = ""
                    for content in event.llm_message.content:
                        # Only include text content in the forwarded message
                        if isinstance(content, TextContent):
                            message_text += content.text

                    # Use the ID from the holder
                    sub_id = sub_conversation_id_holder[0]
                    if sub_id is None:
                        # This should never happen, but guard against it
                        logger.error("Sub-conversation ID not set in callback")
                        return

                    # Send message to parent conversation
                    parent_message = f"[Sub-agent {sub_id[:8]}]: {message_text}"
                    logger.info(
                        f"Sub-agent {sub_id[:8]} sending message "
                        f"to parent: {message_text[:100]}..."
                    )
                    parent_conversation.send_message(
                        Message(
                            role="user",
                            content=[
                                TextContent(
                                    text=parent_message,
                                )
                            ],
                        )
                    )

                    # Trigger parent conversation to run in a separate thread
                    # to avoid blocking the sub-agent thread
                    def run_parent():
                        try:
                            logger.info(
                                f"Sub-agent {sub_id[:8]} triggering "
                                "parent conversation to run"
                            )
                            parent_conversation.run()
                        except Exception as e:
                            logger.error(
                                "Error running parent conversation from sub-agent: %s",
                                e,
                                exc_info=True,
                            )

                    # Start parent run in a new thread so sub-agent can complete
                    # Non-daemon thread so it completes even if main thread is done
                    parent_thread = threading.Thread(target=run_parent, daemon=False)
                    parent_thread.start()

                    # Track parent thread for synchronization
                    parent_id = str(parent_conversation.id)
                    if parent_id not in self.parent_threads:
                        self.parent_threads[parent_id] = []
                    self.parent_threads[parent_id].append(parent_thread)

        # Create sub-conversation with callback
        # Access workspace working_dir to get str path for LocalConversation
        workspace = parent_conversation.state.workspace
        workspace_path = (
            workspace.working_dir
            if isinstance(workspace, LocalWorkspace)
            else str(workspace)
        )

        sub_conversation = LocalConversation(
            agent=worker_agent,
            workspace=workspace_path,
            visualize=visualize,
            callbacks=[sub_agent_completion_callback],
        )

        # Now store the actual conversation ID in the holder
        sub_conversation_id = str(sub_conversation.id)
        sub_conversation_id_holder[0] = sub_conversation_id

        # Store the sub-conversation using its own ID
        self.conversations[sub_conversation_id] = sub_conversation

        # Track parent-child relationship
        parent_id = str(parent_conversation.id)
        self.child_to_parent[sub_conversation_id] = parent_id

        # Start sub-agent in background thread
        def run_sub_agent():
            try:
                logger.info(
                    f"Sub-agent {sub_conversation_id[:8]} starting with task: {task[:100]}..."  # noqa
                )
                # Send initial task to sub-agent
                sub_conversation.send_message(task)
                # Run the sub-agent
                sub_conversation.run()
                logger.info(f"Sub-agent {sub_conversation_id[:8]} completed")
            except Exception as e:
                logger.error(
                    f"Sub-agent {sub_conversation_id[:8]} failed: {e}", exc_info=True
                )
                # Send error message to parent
                parent_conversation.send_message(
                    Message(
                        role="user",
                        content=[
                            TextContent(
                                text=f"[Sub-agent {sub_conversation_id[:8]} ERROR]: {str(e)}",  # noqa
                            )
                        ],
                    )
                )

        thread = threading.Thread(target=run_sub_agent, daemon=False)
        self.sub_agent_threads[sub_conversation_id] = thread
        thread.start()

        logger.info(
            f"Spawned sub-agent {sub_conversation_id[:8]} with task: {task[:100]}..."
        )

        return sub_conversation

    def send_to_sub_agent(self, sub_conversation_id: str, message: str) -> bool:
        """Send a message to a sub-agent.

        Args:
            sub_conversation_id: ID of the sub-conversation
            message: Message to send

        Returns:
            True if message was sent successfully, False otherwise
        """
        sub_conversation = self.conversations.get(sub_conversation_id)
        if sub_conversation is None:
            logger.error(f"Sub-conversation {sub_conversation_id} not found")
            return False

        try:
            sub_conversation.send_message(message)
            logger.debug(
                f"Sent message to sub-agent {sub_conversation_id}: {message[:100]}..."
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to send message to sub-agent {sub_conversation_id}: {e}"
            )
            return False

    def close_sub_agent(self, sub_conversation_id: str) -> bool:
        """Close a sub-agent and clean up resources.

        Args:
            sub_conversation_id: ID of the sub-conversation to close

        Returns:
            True if closed successfully, False otherwise
        """
        if sub_conversation_id not in self.conversations:
            logger.error(f"Sub-conversation {sub_conversation_id} not found")
            return False

        try:
            # Clean up parent-child relationship
            if sub_conversation_id in self.child_to_parent:
                del self.child_to_parent[sub_conversation_id]

            # Remove conversation reference
            del self.conversations[sub_conversation_id]

            logger.info(f"Closed sub-agent {sub_conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to close sub-agent {sub_conversation_id}: {e}")
            return False
