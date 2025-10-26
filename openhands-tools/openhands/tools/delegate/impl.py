"""Implementation of delegate tool executor."""

import threading
from typing import TYPE_CHECKING

from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.logger import get_logger
from openhands.sdk.tool.tool import ToolExecutor
from openhands.tools.delegate.definition import DelegateObservation, SpawnObservation
from openhands.tools.preset.default import get_default_agent


if TYPE_CHECKING:
    from openhands.sdk.conversation.base import BaseConversation
    from openhands.tools.delegate.definition import DelegateAction, SpawnAction

logger = get_logger(__name__)


class DelegateExecutor(ToolExecutor):
    """Simplified executor for delegation operations.

    This class handles:
    - Spawning sub-agents with specific IDs
    - Delegating tasks to sub-agents and waiting for results (blocking)
    """

    def __init__(self, max_children: int = 5):
        self._parent_conversation: BaseConversation | None = None
        self._sub_agents: dict[str, LocalConversation] = {}
        self._max_children: int = max_children
        logger.debug("Initialized DelegateExecutor")

    @property
    def parent_conversation(self) -> "BaseConversation":
        """Get the parent conversation.

        Raises:
            RuntimeError: If parent conversation has not been set yet.
        """
        if self._parent_conversation is None:
            raise RuntimeError(
                "Parent conversation not set. This should be set automatically "
                "on the first call to the executor."
            )
        return self._parent_conversation

    def __call__(
        self, action: "SpawnAction | DelegateAction", conversation: "BaseConversation"
    ) -> "SpawnObservation | DelegateObservation":
        """Execute a spawn or delegate action."""
        # Set parent conversation once on first call
        if self._parent_conversation is None and conversation is not None:
            self._parent_conversation = conversation
            logger.debug(
                f"Set parent conversation {conversation.id} on DelegateExecutor"
            )

        # Route to appropriate handler based on action type
        if hasattr(action, "ids"):  # SpawnAction
            return self._spawn_agents(action)  # type: ignore
        else:  # DelegateAction
            return self._delegate_tasks(action)  # type: ignore

    def _spawn_agents(self, action: "SpawnAction") -> "SpawnObservation":
        """Spawn sub-agents with the given IDs."""
        if not action.ids:
            return SpawnObservation(
                success=False,
                message="At least one ID is required for spawn action",
            )

        if len(action.ids) > self._max_children:
            return SpawnObservation(
                success=False,
                message=(
                    f"Cannot spawn {len(action.ids)} agents, "
                    f"maximum is {self._max_children}"
                ),
            )

        try:
            parent_conversation = self.parent_conversation
            parent_llm = parent_conversation.agent.llm
            visualize = getattr(parent_conversation, "visualize", True)
            workspace_path = parent_conversation.state.workspace.working_dir

            spawned_ids = []
            for agent_id in action.ids:
                # Create a sub-agent with the specified ID
                worker_agent = get_default_agent(
                    llm=parent_llm.model_copy(
                        update={"service_id": f"sub_agent_{agent_id}"}
                    ),
                )

                sub_conversation = LocalConversation(
                    agent=worker_agent,
                    workspace=workspace_path,
                    visualize=visualize,
                    conversation_id=agent_id,
                )

                self._sub_agents[agent_id] = sub_conversation
                spawned_ids.append(agent_id)
                logger.info(f"Spawned sub-agent with ID: {agent_id}")

            agent_list = ", ".join(spawned_ids)
            message = f"Successfully spawned {len(spawned_ids)} sub-agents: {agent_list}"
            return SpawnObservation(
                success=True,
                spawned_ids=spawned_ids,
                message=message,
            )

        except Exception as e:
            logger.error(f"Failed to spawn agents: {e}", exc_info=True)
            return SpawnObservation(
                success=False,
                message=f"Failed to spawn agents: {str(e)}",
            )

    def _delegate_tasks(self, action: "DelegateAction") -> "DelegateObservation":
        """Delegate tasks to sub-agents and wait for results (blocking)."""
        if not action.tasks:
            return DelegateObservation(
                success=False,
                message="At least one task is required for delegate action",
            )

        if len(action.tasks) > len(self._sub_agents):
            return DelegateObservation(
                success=False,
                message=(
                    f"Cannot delegate {len(action.tasks)} tasks to "
                    f"{len(self._sub_agents)} sub-agents. Spawn more agents first."
                ),
            )

        try:
            # Get available sub-agents
            available_agents = list(self._sub_agents.items())[: len(action.tasks)]

            # Create threads to run tasks in parallel
            threads = []
            results = {}
            errors = {}

            def run_task(agent_id: str, conversation: LocalConversation, task: str):
                """Run a single task on a sub-agent."""
                try:
                    logger.info(f"Sub-agent {agent_id} starting task: {task[:100]}...")
                    conversation.send_message(task)
                    conversation.run()

                    # Extract the final response using agent_final_response
                    final_response = conversation.agent_final_response
                    if final_response:
                        results[agent_id] = final_response
                        logger.info(f"Sub-agent {agent_id} completed successfully")
                    else:
                        results[agent_id] = "No response from sub-agent"
                        logger.warning(
                            f"Sub-agent {agent_id} completed but no final response"
                        )

                except Exception as e:
                    error_msg = f"Sub-agent {agent_id} failed: {str(e)}"
                    errors[agent_id] = error_msg
                    logger.error(error_msg, exc_info=True)

            # Start all tasks in parallel
            for i, (agent_id, conversation) in enumerate(available_agents):
                task = action.tasks[i]
                thread = threading.Thread(
                    target=run_task,
                    args=(agent_id, conversation, task),
                    name=f"Task-{agent_id}",
                )
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Collect results
            all_results = []
            success = True

            for i, (agent_id, _) in enumerate(available_agents):
                if agent_id in results:
                    all_results.append(f"Agent {agent_id}: {results[agent_id]}")
                elif agent_id in errors:
                    all_results.append(f"Agent {agent_id} ERROR: {errors[agent_id]}")
                    success = False
                else:
                    all_results.append(f"Agent {agent_id}: No result")
                    success = False

            message = f"Completed delegation of {len(action.tasks)} tasks"
            if errors:
                message += f" with {len(errors)} errors"

            return DelegateObservation(
                success=success,
                results=all_results,
                message=message,
            )

        except Exception as e:
            logger.error(f"Failed to delegate tasks: {e}", exc_info=True)
            return DelegateObservation(
                success=False,
                message=f"Failed to delegate tasks: {str(e)}",
            )

    def is_task_in_progress(self) -> bool:
        """Check if any tasks are in progress.

        Always False for blocking implementation.
        """
        return False
