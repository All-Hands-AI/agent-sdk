"""Implementation of delegate tool executor."""

import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.event import MessageEvent
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.tool.tool import ToolExecutor
from openhands.sdk.workspace import LocalWorkspace


if TYPE_CHECKING:
    from openhands.sdk.conversation.base import BaseConversation
    from openhands.tools.delegate.definition import (
        DelegateAction,
        DelegateObservation,
    )

logger = get_logger(__name__)


class SubAgentState(Enum):
    """States for sub-agent lifecycle."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubAgentInfo:
    """Information about a sub-agent."""

    conversation_id: str
    conversation: "BaseConversation"
    thread: threading.Thread
    state: SubAgentState
    stop_event: threading.Event
    created_at: float
    completed_at: float | None = None
    error: str | None = None


class DelegateExecutor(ToolExecutor):
    """Executor for delegation operations.

    This class handles:
    - Creating sub-agents and their conversations
    - Tracking sub-agents for a single parent conversation
    - Routing messages between parent and child agents
    - Managing sub-agent lifecycle with proper synchronization
    """

    def __init__(self):
        # Thread-safe storage for all state
        self._lock: threading.RLock = threading.RLock()
        self._parent_conversation: BaseConversation | None = None
        self._sub_agents: dict[str, SubAgentInfo] = {}
        self._pending_parent_messages: list[Message] = []

    def __del__(self):
        """Cleanup when executor is destroyed."""
        self.shutdown()

    def shutdown(self):
        """Shutdown the executor and clean up all resources."""
        with self._lock:
            # Cancel all sub-agents
            for sub_agent in list(self._sub_agents.values()):
                self._cancel_sub_agent_unsafe(sub_agent.conversation_id)

            # Clear pending messages
            self._pending_parent_messages.clear()

    def register_conversation(self, conversation: "BaseConversation") -> None:
        """Register the parent conversation with the delegation executor."""
        with self._lock:
            self._parent_conversation = conversation
            logger.debug(f"Registered parent conversation {conversation.id}")

    def get_conversation(self, conversation_id: str) -> "BaseConversation | None":
        """Get the parent conversation if ID matches."""
        with self._lock:
            if (
                self._parent_conversation
                and str(self._parent_conversation.id) == conversation_id
            ):
                return self._parent_conversation
            return None

    def is_task_in_progress(self, conversation_id: str) -> bool:
        """Check if a task started by the parent conversation is still in progress."""
        with self._lock:
            # Only check if this is our parent conversation
            if (
                not self._parent_conversation
                or str(self._parent_conversation.id) != conversation_id
            ):
                return False

            # Clean up dead threads first
            self._cleanup_completed_sub_agents_unsafe()

            # Check for active sub-agents
            for sub_agent in self._sub_agents.values():
                if sub_agent.state in (
                    SubAgentState.CREATED,
                    SubAgentState.RUNNING,
                ):
                    return True

            return False

    def _cleanup_completed_sub_agents_unsafe(self):
        """Clean up completed sub-agents. Must be called with lock held."""
        to_remove = []
        for sub_id, sub_agent in self._sub_agents.items():
            if sub_agent.state in (
                SubAgentState.COMPLETED,
                SubAgentState.FAILED,
                SubAgentState.CANCELLED,
            ):
                if not sub_agent.thread.is_alive():
                    to_remove.append(sub_id)

        for sub_id in to_remove:
            logger.debug(f"Cleaning up completed sub-agent {sub_id[:8]}")
            del self._sub_agents[sub_id]

    def __call__(
        self, action: "DelegateAction", conversation: "BaseConversation"
    ) -> "DelegateObservation":
        """Execute a delegation action."""
        from openhands.tools.delegate.definition import DelegateObservation

        if action.operation == "spawn":
            return self._spawn_sub_agent(action, conversation)
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

    def _trigger_parent_if_idle(self):
        """
        Core rule: If parent.state.agent_status == FINISHED and there are pending
        child outputs queued for the parent, then trigger exactly one
        parent_conversation.run().

        This provides:
        - No re-entrancy: only fire when parent is idle
        - Natural batching: all messages that arrive while parent is busy are
          processed together
        - Lower latency than fixed debounce: run as soon as parent flips to idle
        - Cost control: at most one extra parent run per idle transition
        """
        with self._lock:
            if not self._parent_conversation:
                return

            if not self._pending_parent_messages:
                return

            # Check if parent is idle (FINISHED state)
            try:
                if hasattr(self._parent_conversation, "state") and hasattr(
                    self._parent_conversation.state, "agent_status"
                ):
                    if self._parent_conversation.state.agent_status == "FINISHED":
                        # Parent is idle and we have pending messages - trigger one run
                        messages_to_send = self._pending_parent_messages.copy()
                        self._pending_parent_messages.clear()

                        # Send all pending messages to parent
                        for message in messages_to_send:
                            try:
                                self._parent_conversation.send_message(message)
                                logger.debug(
                                    f"Sent message to parent "
                                    f"{self._parent_conversation.id}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Failed to send message to parent "
                                    f"{self._parent_conversation.id}: {e}"
                                )

                        # Trigger exactly one parent run to process all messages
                        try:
                            self._parent_conversation.run()
                            logger.debug(
                                f"Triggered parent conversation run for "
                                f"{self._parent_conversation.id}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to trigger parent conversation run: {e}"
                            )

            except Exception as e:
                logger.error(f"Error checking parent status: {e}")

    def _spawn_sub_agent(
        self, action: "DelegateAction", conversation: "BaseConversation"
    ) -> "DelegateObservation":
        """Spawn a new sub-agent that runs asynchronously."""
        from openhands.tools.delegate.definition import DelegateObservation

        if not action.message:
            return DelegateObservation(
                operation="spawn",
                success=False,
                message="Message is required for spawn operation",
            )

        try:
            # Register parent conversation if not already registered
            with self._lock:
                if self._parent_conversation is None:
                    self.register_conversation(conversation)
                parent_conversation = self._parent_conversation

            from openhands.tools.preset.default import get_default_agent

            # Ensure parent conversation has agent attribute
            assert hasattr(parent_conversation, "agent"), (
                "Parent conversation must have agent attribute"
            )
            parent_agent = parent_conversation.agent
            assert hasattr(parent_agent, "llm"), "Parent agent must have llm attribute"

            parent_llm = parent_agent.llm
            cli_mode = getattr(
                parent_agent,
                "cli_mode",
                False,
            ) or not hasattr(parent_conversation, "workspace")

            worker_agent = get_default_agent(
                llm=parent_llm.model_copy(update={"service_id": "sub_agent"}),
                cli_mode=cli_mode,
            )

            visualize = getattr(parent_conversation, "visualize", True)

            # Generate unique sub-conversation ID
            sub_conversation_id = str(uuid.uuid4())

            stop_event = threading.Event()

            def sub_agent_completion_callback(event):
                """Callback for sub-agent messages - queues them for parent."""
                if isinstance(event, MessageEvent) and event.source == "agent":
                    if hasattr(event, "llm_message") and event.llm_message:
                        # Extract all content types properly
                        message_parts = []
                        for content in event.llm_message.content:
                            if isinstance(content, TextContent):
                                message_parts.append(content.text)
                            else:
                                # Handle other content types
                                message_parts.append(f"[{type(content).__name__}]")

                        message_text = " ".join(message_parts)

                        if message_text.strip():
                            parent_message = (
                                f"[Sub-agent {sub_conversation_id[:8]}]: {message_text}"
                            )
                            logger.info(
                                f"Sub-agent {sub_conversation_id[:8]} sending message "
                                f"to parent: {message_text[:100]}..."
                            )

                            # Queue message for parent and trigger if idle
                            message = Message(
                                role="user",
                                content=[TextContent(text=parent_message)],
                            )
                            self._pending_parent_messages.append(message)

                            # Trigger parent if it's idle
                            self._trigger_parent_if_idle()

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

            def run_sub_agent():
                """Sub-agent thread function with proper error handling and state management."""  # noqa: E501
                try:
                    with self._lock:
                        if sub_conversation_id in self._sub_agents:
                            self._sub_agents[
                                sub_conversation_id
                            ].state = SubAgentState.RUNNING

                    # action.message is guaranteed to be not None due to check above
                    assert action.message is not None
                    logger.info(
                        f"Sub-agent {sub_conversation_id[:8]} starting with task: "
                        f"{action.message[:100]}..."
                    )

                    # Send initial message and run
                    sub_conversation.send_message(action.message)

                    # Run with cancellation support
                    while not stop_event.is_set():
                        try:
                            # Run conversation step with timeout
                            sub_conversation.run()
                            break  # Conversation completed normally
                        except Exception as e:
                            if stop_event.is_set():
                                logger.info(
                                    f"Sub-agent {sub_conversation_id[:8]} cancelled"
                                )
                                break
                            raise e

                    if not stop_event.is_set():
                        logger.info(
                            f"Sub-agent {sub_conversation_id[:8]} completed "
                            "successfully"
                        )
                        with self._lock:
                            if sub_conversation_id in self._sub_agents:
                                self._sub_agents[
                                    sub_conversation_id
                                ].state = SubAgentState.COMPLETED
                                self._sub_agents[
                                    sub_conversation_id
                                ].completed_at = time.time()
                    else:
                        with self._lock:
                            if sub_conversation_id in self._sub_agents:
                                self._sub_agents[
                                    sub_conversation_id
                                ].state = SubAgentState.CANCELLED
                                self._sub_agents[
                                    sub_conversation_id
                                ].completed_at = time.time()

                except Exception as e:
                    logger.error(
                        f"Sub-agent {sub_conversation_id[:8]} failed: {e}",
                        exc_info=True,
                    )

                    # Send error message to parent
                    error_message = (
                        f"[Sub-agent {sub_conversation_id[:8]} ERROR]: {str(e)}"
                    )
                    message = Message(
                        role="user",
                        content=[TextContent(text=error_message)],
                    )
                    with self._lock:
                        self._pending_parent_messages.append(message)
                        # Trigger parent if it's idle
                        self._trigger_parent_if_idle()

                    with self._lock:
                        if sub_conversation_id in self._sub_agents:
                            self._sub_agents[
                                sub_conversation_id
                            ].state = SubAgentState.FAILED
                            self._sub_agents[sub_conversation_id].error = str(e)
                            self._sub_agents[
                                sub_conversation_id
                            ].completed_at = time.time()

            # Create and start thread
            thread = threading.Thread(
                target=run_sub_agent,
                name=f"SubAgent-{sub_conversation_id[:8]}",
                daemon=False,
            )

            # Create sub-agent info and register it
            sub_agent_info = SubAgentInfo(
                conversation_id=sub_conversation_id,
                conversation=sub_conversation,
                thread=thread,
                state=SubAgentState.CREATED,
                stop_event=stop_event,
                created_at=time.time(),
            )

            with self._lock:
                self._sub_agents[sub_conversation_id] = sub_agent_info

            thread.start()

            logger.info(
                f"Spawned sub-agent {sub_conversation_id[:8]} with task: "
                f"{action.message[:100]}..."
            )

            return DelegateObservation(
                operation="spawn",
                success=True,
                sub_conversation_id=sub_conversation_id,
                message=(
                    f"Sub-agent {sub_conversation_id} created and running "
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
        from openhands.tools.delegate.definition import DelegateObservation

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

        with self._lock:
            sub_agent = self._sub_agents.get(action.sub_conversation_id)
            if sub_agent is None:
                logger.error(f"Sub-agent {action.sub_conversation_id} not found")
                return DelegateObservation(
                    operation="send",
                    success=False,
                    sub_conversation_id=action.sub_conversation_id,
                    message=(
                        f"Failed to send message to sub-agent "
                        f"{action.sub_conversation_id}"
                    ),
                )

            if sub_agent.state not in (SubAgentState.CREATED, SubAgentState.RUNNING):
                return DelegateObservation(
                    operation="send",
                    success=False,
                    sub_conversation_id=action.sub_conversation_id,
                    message=(
                        f"Sub-agent {action.sub_conversation_id} is not active "
                        f"(state: {sub_agent.state.value})"
                    ),
                )

        try:
            # Send message to sub-agent's conversation
            sub_agent.conversation.send_message(action.message)
            logger.debug(
                f"Sent message to sub-agent {action.sub_conversation_id}: "
                f"{action.message[:100]}..."
            )
            return DelegateObservation(
                operation="send",
                success=True,
                sub_conversation_id=action.sub_conversation_id,
                message=f"Message sent to sub-agent {action.sub_conversation_id}",
            )
        except Exception as e:
            logger.error(
                f"Failed to send message to sub-agent {action.sub_conversation_id}: {e}"
            )
            return DelegateObservation(
                operation="send",
                success=False,
                sub_conversation_id=action.sub_conversation_id,
                message=(
                    f"Failed to send message to sub-agent "
                    f"{action.sub_conversation_id}: {e}"
                ),
            )

    def _close_sub_agent(self, action: "DelegateAction") -> "DelegateObservation":
        """Close a sub-agent properly with thread cleanup."""
        from openhands.tools.delegate.definition import DelegateObservation

        if not action.sub_conversation_id:
            return DelegateObservation(
                operation="close",
                success=False,
                message="Sub-conversation ID is required for close operation",
            )

        with self._lock:
            sub_agent = self._sub_agents.get(action.sub_conversation_id)
            if sub_agent is None:
                logger.error(f"Sub-agent {action.sub_conversation_id} not found")
                return DelegateObservation(
                    operation="close",
                    success=False,
                    sub_conversation_id=action.sub_conversation_id,
                    message=f"Sub-agent {action.sub_conversation_id} not found",
                )

        try:
            return self._cancel_sub_agent_unsafe(action.sub_conversation_id)
        except Exception as e:
            logger.error(f"Failed to close sub-agent {action.sub_conversation_id}: {e}")
            return DelegateObservation(
                operation="close",
                success=False,
                sub_conversation_id=action.sub_conversation_id,
                message=f"Failed to close sub-agent {action.sub_conversation_id}: {e}",
            )

    def _cancel_sub_agent_unsafe(
        self, sub_conversation_id: str
    ) -> "DelegateObservation":
        """Cancel a sub-agent. Must be called with lock held."""
        from openhands.tools.delegate.definition import DelegateObservation

        sub_agent = self._sub_agents.get(sub_conversation_id)
        if sub_agent is None:
            return DelegateObservation(
                operation="close",
                success=False,
                sub_conversation_id=sub_conversation_id,
                message=f"Sub-agent {sub_conversation_id} not found",
            )

        # Signal the sub-agent to stop
        sub_agent.stop_event.set()
        sub_agent.state = SubAgentState.CANCELLED
        sub_agent.completed_at = time.time()

        # Wait for thread to finish (with timeout)
        if sub_agent.thread.is_alive():
            logger.info(f"Waiting for sub-agent {sub_conversation_id[:8]} to stop...")
            # Release lock temporarily to avoid deadlock
            self._lock.release()
            try:
                sub_agent.thread.join(timeout=10.0)
                if sub_agent.thread.is_alive():
                    logger.warning(
                        f"Sub-agent {sub_conversation_id[:8]} did not stop gracefully"
                    )
            finally:
                self._lock.acquire()

        logger.info(f"Closed sub-agent {sub_conversation_id[:8]}")
        return DelegateObservation(
            operation="close",
            success=True,
            sub_conversation_id=sub_conversation_id,
            message=f"Sub-agent {sub_conversation_id} closed successfully",
        )
