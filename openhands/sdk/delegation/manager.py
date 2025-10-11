"""DelegationManager for handling agent delegation and message routing."""

import uuid
from typing import TYPE_CHECKING, Any

from openhands.sdk.logger import get_logger


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
    """

    def __init__(self):
        # Store conversation references to prevent garbage collection
        self.conversations: dict[str, BaseConversation | dict[str, Any]] = {}
        # Track parent-child relationships
        self.parent_to_children: dict[str, set[str]] = {}
        self.child_to_parent: dict[str, str] = {}

    def spawn_sub_agent(
        self,
        parent_conversation: "BaseConversation",
        task: str,
        worker_agent: "AgentBase",
    ) -> "BaseConversation":
        """Spawn a sub-agent with a new conversation.

        Args:
            parent_conversation: The parent conversation
            task: The task description for the sub-agent
            worker_agent: The worker agent to use for the sub-conversation

        Returns:
            The new sub-conversation
        """
        # TODO: Implement full conversation creation
        # For now, this is not used - we use create_simple_sub_agent instead
        raise NotImplementedError("Full conversation spawning not yet implemented")

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
            # Handle both dict-based simple agents and real conversation objects
            if isinstance(sub_conversation, dict):
                # Simple agent - just store the message
                if "messages" not in sub_conversation:
                    sub_conversation["messages"] = []
                sub_conversation["messages"].append(message)
                logger.debug(
                    f"Sent message to simple sub-agent {sub_conversation_id}: "
                    f"{message[:100]}..."
                )
            else:
                # Real conversation object
                sub_conversation.send_message(message)  # type: ignore
                logger.debug(
                    f"Sent message to sub-agent {sub_conversation_id}: "
                    f"{message[:100]}..."
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
            # Get parent ID before cleanup
            parent_id = self.child_to_parent.get(sub_conversation_id)

            # Clean up relationships
            if parent_id and parent_id in self.parent_to_children:
                self.parent_to_children[parent_id].discard(sub_conversation_id)
                if not self.parent_to_children[parent_id]:
                    del self.parent_to_children[parent_id]

            if sub_conversation_id in self.child_to_parent:
                del self.child_to_parent[sub_conversation_id]

            # Remove conversation reference (works for both dict and conversation objects)  # noqa: E501
            del self.conversations[sub_conversation_id]

            logger.info(f"Closed sub-agent {sub_conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to close sub-agent {sub_conversation_id}: {e}")
            return False

    def get_sub_agents(self, parent_conversation_id: str) -> list[str]:
        """Get list of sub-agent IDs for a parent conversation.

        Args:
            parent_conversation_id: ID of the parent conversation

        Returns:
            List of sub-agent conversation IDs
        """
        return list(self.parent_to_children.get(parent_conversation_id, set()))

    def is_sub_agent(self, conversation_id: str) -> bool:
        """Check if a conversation is a sub-agent.

        Args:
            conversation_id: ID of the conversation to check

        Returns:
            True if it's a sub-agent, False otherwise
        """
        return conversation_id in self.child_to_parent

    def get_parent_id(self, sub_conversation_id: str) -> str | None:
        """Get the parent conversation ID for a sub-agent.

        Args:
            sub_conversation_id: ID of the sub-conversation

        Returns:
            Parent conversation ID or None if not found
        """
        return self.child_to_parent.get(sub_conversation_id)

    def _create_message_router(self, parent_conversation: "BaseConversation"):
        """Create a callback function that routes sub-agent messages to parent.

        Args:
            parent_conversation: The parent conversation to route messages to

        Returns:
            Callback function for message routing
        """
        # TODO: Implement message routing for full conversation spawning
        # For now, this is not used - we use simple sub-agents instead
        raise NotImplementedError("Message routing not yet implemented")

    def create_simple_sub_agent(self, task: str) -> str:
        """Create a simple sub-agent for demonstration purposes."""

        # Generate a unique ID for the sub-agent
        sub_conversation_id = str(uuid.uuid4())

        # For now, just store the task and return the ID
        # In a full implementation, this would create an actual conversation
        self.conversations[sub_conversation_id] = {
            "task": task,
            "status": "created",
            "messages": [],
        }

        logger.info(f"Created simple sub-agent {sub_conversation_id} with task: {task}")
        return sub_conversation_id

    def send_simple_message(self, sub_conversation_id: str, message: str) -> bool:
        """Send a message to a simple sub-agent."""
        if sub_conversation_id not in self.conversations:
            logger.error(f"Sub-conversation {sub_conversation_id} not found")
            return False

        # Store the message in the simple sub-agent
        sub_agent = self.conversations[sub_conversation_id]
        if isinstance(sub_agent, dict):
            sub_agent["messages"].append(message)
            logger.info(
                f"Sent message to simple sub-agent {sub_conversation_id}: {message}"
            )
            return True

        return False
