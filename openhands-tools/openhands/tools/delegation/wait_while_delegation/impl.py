"""Implementation of wait while delegation tool executor."""

from typing import TYPE_CHECKING

from openhands.sdk.logger import get_logger
from openhands.sdk.tool.tool import ToolExecutor


if TYPE_CHECKING:
    from openhands.tools.delegation.wait_while_delegation.definition import (
        WaitWhileDelegationAction,
        WaitWhileDelegationObservation,
    )

logger = get_logger(__name__)


class WaitWhileDelegationExecutor(ToolExecutor):
    """Executor for waiting while sub-agents complete their tasks."""

    def __call__(
        self, action: "WaitWhileDelegationAction"
    ) -> "WaitWhileDelegationObservation":
        """Execute wait while delegation action by pausing the conversation.

        This tool is similar to the finish tool - it signals that the main agent
        should pause and wait for sub-agents to complete their work. The conversation
        status will be set to FINISHED in the agent logic, just like with finish.
        """
        from openhands.tools.delegation.wait_while_delegation.definition import (
            WaitWhileDelegationObservation,
        )

        logger.info(f"Main agent pausing: {action.message}")

        # Return observation that indicates the main agent is waiting
        # The agent logic will detect this tool and set status to FINISHED
        return WaitWhileDelegationObservation()
