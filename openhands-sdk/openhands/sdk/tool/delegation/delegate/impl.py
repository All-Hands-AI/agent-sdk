"""Implementation of delegate tool executor."""

from typing import TYPE_CHECKING

from openhands.sdk.delegation.manager import DelegationManager
from openhands.sdk.logger import get_logger
from openhands.sdk.tool.tool import ToolExecutor


if TYPE_CHECKING:
    from openhands.sdk.tool.delegation.delegate.definition import (
        DelegateAction,
        DelegateObservation,
    )

logger = get_logger(__name__)

# Use singleton instance
DELEGATION_MANAGER = DelegationManager()


class DelegateExecutor(ToolExecutor):
    """Executor for delegation operations."""

    def __call__(self, action: "DelegateAction", conversation) -> "DelegateObservation":
        """Execute a delegation action."""
        from openhands.sdk.tool.delegation.delegate.definition import (
            DelegateObservation,
        )

        if action.operation == "spawn":
            return self._spawn_sub_agent(action)
        elif action.operation == "send":
            return self._send_to_sub_agent(action)
        elif action.operation == "close":
            return self._close_sub_agent(action)
        else:
            return DelegateObservation(
                operation=action.operation,
                success=False,
                message=f"Unknown operation: {action.operation}",
            )

    def _spawn_sub_agent(self, action: "DelegateAction") -> "DelegateObservation":
        """Spawn a new sub-agent that runs asynchronously.

        The sub-agent will run in a separate thread and send messages back to the
        parent conversation when it completes or needs input.
        """
        from openhands.sdk.tool.delegation.delegate.definition import (
            DelegateObservation,
        )

        if not action.task:
            return DelegateObservation(
                operation="spawn",
                success=False,
                message="Task is required for spawn operation",
            )

        # Check if conversation context is available
        if not action.conversation_id:
            logger.error("Conversation ID not set in action")
            return DelegateObservation(
                operation="spawn",
                success=False,
                message=(
                    "Delegation not properly configured - conversation ID missing"
                ),
            )

        try:
            # Get parent conversation from delegation manager
            parent_conversation = DELEGATION_MANAGER.get_conversation(
                str(action.conversation_id)
            )
            if parent_conversation is None:
                return DelegateObservation(
                    operation="spawn",
                    success=False,
                    message=f"Parent conversation {action.conversation_id} not found",
                )

            from openhands.tools.preset.default import get_default_agent

            # Get the parent agent's LLM to use for worker
            # Type ignore because BaseConversation protocol doesn't expose agent
            # but LocalConversation does have it
            parent_llm = parent_conversation.agent.llm  # type: ignore[attr-defined]
            cli_mode = getattr(
                parent_conversation.agent,  # type: ignore[attr-defined]
                "cli_mode",
                False,
            ) or not hasattr(parent_conversation, "workspace")

            # Create worker agent (default agent with delegation disabled)
            worker_agent = get_default_agent(
                llm=parent_llm.model_copy(update={"service_id": "sub_agent"}),
                cli_mode=cli_mode,
                enable_delegation=False,
            )

            # Get visualize setting from parent conversation (default True)
            visualize = getattr(parent_conversation, "visualize", True)

            # Spawn the sub-agent with real conversation (non-blocking)
            sub_conversation = DELEGATION_MANAGER.spawn_sub_agent(
                parent_conversation=parent_conversation,
                task=action.task,
                worker_agent=worker_agent,
                visualize=visualize,
            )

            logger.info(
                "Spawned sub-agent %s for task: %s...",
                sub_conversation.id,
                action.task[:100],
            )

            return DelegateObservation(
                operation="spawn",
                success=True,
                sub_conversation_id=str(sub_conversation.id),
                message=(
                    f"Sub-agent {sub_conversation.id} created and running "
                    "asynchronously"
                ),
            )

        except Exception as e:
            logger.error(f"Failed to spawn sub-agent: {e}", exc_info=True)
            return DelegateObservation(
                operation="spawn",
                success=False,
                message=f"Failed to spawn sub-agent: {str(e)}",
            )

    def _send_to_sub_agent(self, action: "DelegateAction") -> "DelegateObservation":
        """Send a message to a sub-agent."""
        from openhands.sdk.tool.delegation.delegate.definition import (
            DelegateObservation,
        )

        if not action.sub_conversation_id:
            return DelegateObservation(
                operation="send",
                success=False,
                message="Sub-conversation ID is required for send operation",
            )

        if not action.message:
            return DelegateObservation(
                operation="send",
                success=False,
                message="Message is required for send operation",
            )

        # Send message to sub-agent
        success = DELEGATION_MANAGER.send_to_sub_agent(
            sub_conversation_id=action.sub_conversation_id, message=action.message
        )

        if success:
            return DelegateObservation(
                operation="send",
                success=True,
                sub_conversation_id=action.sub_conversation_id,
                message=f"Message sent to sub-agent {action.sub_conversation_id}",
            )
        else:
            return DelegateObservation(
                operation="send",
                success=False,
                sub_conversation_id=action.sub_conversation_id,
                message=(
                    f"Failed to send message to sub-agent {action.sub_conversation_id}"
                ),
            )

    def _close_sub_agent(self, action: "DelegateAction") -> "DelegateObservation":
        """Close a sub-agent."""
        from openhands.sdk.tool.delegation.delegate.definition import (
            DelegateObservation,
        )

        if not action.sub_conversation_id:
            return DelegateObservation(
                operation="close",
                success=False,
                message="Sub-conversation ID is required for close operation",
            )

        success = DELEGATION_MANAGER.close_sub_agent(
            sub_conversation_id=action.sub_conversation_id
        )

        if success:
            return DelegateObservation(
                operation="close",
                success=True,
                sub_conversation_id=action.sub_conversation_id,
                message=f"Sub-agent {action.sub_conversation_id} closed successfully",
            )
        else:
            return DelegateObservation(
                operation="close",
                success=False,
                sub_conversation_id=action.sub_conversation_id,
                message=f"Failed to close sub-agent {action.sub_conversation_id}",
            )
