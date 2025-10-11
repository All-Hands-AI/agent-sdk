"""Implementation of delegation tool executor."""

from typing import TYPE_CHECKING

from openhands.sdk.delegation.manager import DelegationManager
from openhands.sdk.logger import get_logger
from openhands.sdk.tool.tool import ToolExecutor


if TYPE_CHECKING:
    from openhands.tools.delegation.definition import (
        DelegateAction,
        DelegateObservation,
    )

logger = get_logger(__name__)


class DelegateExecutor(ToolExecutor):
    """Executor for delegation operations."""

    def __init__(self):
        self.delegation_manager = DelegationManager()

    def __call__(self, action: "DelegateAction") -> "DelegateObservation":
        """Execute a delegation action."""
        from openhands.tools.delegation.definition import DelegateObservation

        if action.operation == "spawn":
            return self._spawn_sub_agent(action)
        elif action.operation == "send":
            return self._send_to_sub_agent(action)
        elif action.operation == "status":
            return self._get_sub_agent_status(action)
        elif action.operation == "close":
            return self._close_sub_agent(action)
        else:
            return DelegateObservation(
                status="error", message=f"Unknown operation: {action.operation}"
            )

    def _spawn_sub_agent(self, action: "DelegateAction") -> "DelegateObservation":
        """Spawn a new sub-agent."""
        from openhands.tools.delegation.definition import DelegateObservation

        if not action.task:
            return DelegateObservation(
                status="error", message="Task is required for spawn operation"
            )

        try:
            # For now, create a simple sub-agent without parent conversation wiring
            # This is a simplified implementation for demonstration
            sub_conversation_id = self.delegation_manager.create_simple_sub_agent(
                action.task
            )

            return DelegateObservation(
                sub_conversation_id=sub_conversation_id,
                status="created",
                message=(
                    f"Sub-agent created successfully with ID: {sub_conversation_id}"
                ),
                result=f"Task assigned: {action.task}",
            )

        except Exception as e:
            logger.error(f"Failed to spawn sub-agent: {e}")
            return DelegateObservation(
                status="error", message=f"Failed to spawn sub-agent: {str(e)}"
            )

    def _send_to_sub_agent(self, action: "DelegateAction") -> "DelegateObservation":
        """Send a message to a sub-agent."""
        from openhands.tools.delegation.definition import DelegateObservation

        if not action.sub_conversation_id:
            return DelegateObservation(
                status="error",
                message="Sub-conversation ID is required for send operation",
            )

        if not action.message:
            return DelegateObservation(
                status="error", message="Message is required for send operation"
            )

        # For simplified implementation, just store the message
        success = self.delegation_manager.send_simple_message(
            sub_conversation_id=action.sub_conversation_id, message=action.message
        )

        if success:
            return DelegateObservation(
                sub_conversation_id=action.sub_conversation_id,
                status="message_sent",
                message=f"Message sent to sub-agent {action.sub_conversation_id}",
                result=f"Message: {action.message}",
            )
        else:
            return DelegateObservation(
                sub_conversation_id=action.sub_conversation_id,
                status="error",
                message=(
                    f"Failed to send message to sub-agent {action.sub_conversation_id}"
                ),
            )

    def _get_sub_agent_status(self, action: "DelegateAction") -> "DelegateObservation":
        """Get the status of a sub-agent."""
        from openhands.tools.delegation.definition import DelegateObservation

        if not action.sub_conversation_id:
            return DelegateObservation(
                status="error",
                message="Sub-conversation ID is required for status operation",
            )

        # Check if sub-agent exists
        if action.sub_conversation_id not in self.delegation_manager.conversations:
            return DelegateObservation(
                sub_conversation_id=action.sub_conversation_id,
                status="not_found",
                message=f"Sub-agent {action.sub_conversation_id} not found",
            )

        # Get simple sub-agent and check its status
        sub_agent = self.delegation_manager.conversations[action.sub_conversation_id]
        if isinstance(sub_agent, dict):
            agent_status = sub_agent.get("status", "unknown")
            return DelegateObservation(
                sub_conversation_id=action.sub_conversation_id,
                status="active",
                message=f"Sub-agent {action.sub_conversation_id} is {agent_status}",
                result=(
                    f"Agent status: {agent_status}, "
                    f"Task: {sub_agent.get('task', 'N/A')}"
                ),
            )
        else:
            # Real conversation object
            agent_status = sub_agent.state.agent_status
            return DelegateObservation(
                sub_conversation_id=action.sub_conversation_id,
                status="active",
                message=(
                    f"Sub-agent {action.sub_conversation_id} is {agent_status.value}"
                ),
                result=f"Agent status: {agent_status.value}",
            )

    def _close_sub_agent(self, action: "DelegateAction") -> "DelegateObservation":
        """Close a sub-agent."""
        from openhands.tools.delegation.definition import DelegateObservation

        if not action.sub_conversation_id:
            return DelegateObservation(
                status="error",
                message="Sub-conversation ID is required for close operation",
            )

        success = self.delegation_manager.close_sub_agent(
            sub_conversation_id=action.sub_conversation_id
        )

        if success:
            return DelegateObservation(
                sub_conversation_id=action.sub_conversation_id,
                status="closed",
                message=f"Sub-agent {action.sub_conversation_id} closed successfully",
            )
        else:
            return DelegateObservation(
                sub_conversation_id=action.sub_conversation_id,
                status="error",
                message=f"Failed to close sub-agent {action.sub_conversation_id}",
            )

    def set_parent_conversation(self, conversation):
        """Set the parent conversation for this executor."""
        self._parent_conversation = conversation
