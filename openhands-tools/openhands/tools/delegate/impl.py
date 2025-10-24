"""Implementation of delegate tool executor."""

import queue
import threading
import time
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, ConfigDict

from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.event import MessageEvent
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.tool.tool import ToolExecutor
from openhands.tools.delegate.definition import DelegateObservation
from openhands.tools.preset.default import get_default_agent


if TYPE_CHECKING:
    from openhands.sdk.conversation.base import BaseConversation
    from openhands.tools.delegate.definition import DelegateAction

logger = get_logger(__name__)


class SubAgentState(Enum):
    """States for sub-agent lifecycle."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubAgentInfo(BaseModel):
    """Information about a sub-agent."""

    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)

    conversation_id: str
    conversation: Any  # BaseConversation - using Any to avoid forward reference issues
    thread: Any  # threading.Thread - using Any for runtime objects
    state: SubAgentState
    stop_event: Any  # threading.Event - using Any for runtime objects
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

    def __init__(self, max_children: int = 10):
        # Thread-safe storage for all state
        self._lock: threading.RLock = threading.RLock()
        self._parent_conversation: BaseConversation | None = None
        self._sub_agents: dict[str, SubAgentInfo] = {}
        self._pending_parent_messages: queue.Queue[Message] = queue.Queue(maxsize=1000)
        self._parent_running: bool = False  # Single-flight guard for parent runs
        self._max_children: int = max_children  # Limit concurrent sub-agents
        logger.debug("Initialized DelegateExecutor")

    @property
    def parent_conversation(self) -> "LocalConversation":
        """Get the parent conversation.

        Raises:
            RuntimeError: If parent conversation has not been set yet.
        """
        if self._parent_conversation is None:
            raise RuntimeError(
                "Parent conversation not set. This should be set automatically "
                "on the first call to the executor."
            )
        return self._parent_conversation  # type: ignore

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cleanup."""
        self.shutdown()
        return False

    def shutdown(self):
        """Shutdown the executor and clean up all resources."""
        # Get list of sub-agents to cancel (outside lock to avoid deadlock)
        with self._lock:
            sub_agent_ids = list(self._sub_agents.keys())

        # Cancel all sub-agents (this will join threads outside lock)
        for sub_agent_id in sub_agent_ids:
            self._cancel_sub_agent(sub_agent_id)

        with self._lock:
            # Clear pending messages
            while not self._pending_parent_messages.empty():
                try:
                    self._pending_parent_messages.get_nowait()
                except queue.Empty:
                    break

    def is_task_in_progress(self) -> bool:
        """Check if a task started by the parent conversation is still in progress."""
        with self._lock:
            self._cleanup_completed_sub_agents_unsafe()

            parent_running = (
                self.parent_conversation.state.agent_status
                != AgentExecutionStatus.FINISHED
            )
            if parent_running:
                return True

            pending_messages = self._pending_parent_messages.qsize()
            if pending_messages > 0:
                return True

            active_sub_agents = sum(
                1
                for sub_agent in self._sub_agents.values()
                if sub_agent.state in (SubAgentState.CREATED, SubAgentState.RUNNING)
            )
            if active_sub_agents > 0:
                return True

            return False

    def _cleanup_completed_sub_agents_unsafe(self):
        """Clean up completed sub-agents. Must be called with lock held."""
        logger.info(f"Starting cleanup of {len(self._sub_agents)} sub-agents")
        to_remove = []
        for sub_id, sub_agent in self._sub_agents.items():
            if sub_agent.state in (
                SubAgentState.COMPLETED,
                SubAgentState.FAILED,
                SubAgentState.CANCELLED,
            ):
                logger.info(
                    f"Checking cleanup for {sub_id[:8]} in state {sub_agent.state}"
                )
                # Try to join the thread with a short timeout
                if sub_agent.thread.is_alive():
                    try:
                        logger.info(f"Attempting to join thread for {sub_id[:8]}")
                        sub_agent.thread.join(timeout=0.1)  # 100ms timeout
                    except Exception as e:
                        logger.info(f"Error joining thread for {sub_id[:8]}: {e}")

                # If thread is now dead or was already dead, clean it up
                if not sub_agent.thread.is_alive():
                    logger.info(f"Thread for {sub_id[:8]} is dead, marking for removal")
                    to_remove.append(sub_id)
                else:
                    # Thread is still alive but sub-agent is completed
                    # This might indicate a stuck thread - log it
                    runtime = time.time() - sub_agent.created_at
                    logger.warning(
                        f"Sub-agent {sub_id[:8]} is {sub_agent.state} "
                        f"but thread is still alive after {runtime:.1f}s"
                    )
                    # If it's been more than 10 seconds, force cleanup
                    if time.time() - sub_agent.created_at > 10:
                        logger.warning(
                            f"Force cleaning up stuck sub-agent {sub_id[:8]} "
                            f"after {runtime:.1f}s"
                        )
                        to_remove.append(sub_id)

        logger.info(f"Removing {len(to_remove)} completed sub-agents")
        for sub_id in to_remove:
            logger.info(f"Cleaning up completed sub-agent {sub_id[:8]}")
            del self._sub_agents[sub_id]

    def __call__(
        self, action: "DelegateAction", conversation: "BaseConversation"
    ) -> "DelegateObservation":
        """Execute a delegation action."""
        # Set parent conversation once on first call
        if self._parent_conversation is None and conversation is not None:
            self._parent_conversation = conversation
            logger.debug(
                f"Set parent conversation {conversation.id} on DelegateExecutor"
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
        - Cost control: at most one extra parent run per idle transitions
        """
        logger.debug("🔍 _trigger_parent_if_idle called")

        # Check conditions and collect messages under lock
        with self._lock:
            queue_size = self._pending_parent_messages.qsize()
            if self._pending_parent_messages.empty():
                logger.debug("❌ No pending parent messages")
                return

            logger.info(f"📬 Found {queue_size} pending parent messages")

            # Single-flight guard - prevent concurrent parent runs
            if self._parent_running:
                logger.info("❌ Parent already running, skipping trigger")
                return

            # Check if parent is finished
            try:
                status = self.parent_conversation.state.agent_status

                # Parent should be in FINISHED or IDLE state to be resumed
                if status not in (AgentExecutionStatus.FINISHED,):
                    logger.info(
                        f"❌ Parent not in FINISHED/IDLE state ({status}), "
                        f"not triggering run"
                    )
                    return

                logger.info(
                    f"✅ Parent is {status} with {queue_size} pending messages, "
                    f"triggering run"
                )

                # Parent is idle, we have messages, and no run in progress
                # Set running flag and drain queue
                self._parent_running = True
                messages_to_send = []
                while not self._pending_parent_messages.empty():
                    try:
                        messages_to_send.append(
                            self._pending_parent_messages.get_nowait()
                        )
                    except queue.Empty:
                        break

                parent_conversation = self.parent_conversation

            except Exception as e:
                logger.error(f"Error checking parent status: {e}")
                return

        # Send messages and trigger parent run outside of lock
        try:
            # Send all pending messages to parent
            for message in messages_to_send:
                try:
                    parent_conversation.send_message(message)
                    logger.debug(f"Sent message to parent {parent_conversation.id}")
                except Exception as e:
                    logger.error(
                        f"Failed to send message to parent "
                        f"{parent_conversation.id}: {e}"
                    )

            # Trigger exactly one parent run to process all messages
            try:
                logger.info(
                    f"🔄 Triggering parent conversation run for "
                    f"{parent_conversation.id} with {len(messages_to_send)} messages"
                )
                parent_conversation.run()
                logger.info(
                    f"✅ Parent conversation run completed for {parent_conversation.id}"
                )
            except Exception as e:
                logger.error(f"Failed to trigger parent conversation run: {e}")
        finally:
            # Always clear the running flag
            with self._lock:
                self._parent_running = False

            # CRITICAL: Check for additional pending messages after parent completes
            # This handles the race condition where messages arrive while parent
            # was running
            logger.debug("🔄 Checking for additional pending messages after parent run")
            self._trigger_parent_if_idle()

    def _create_sub_agent_callback(self, sub_conversation_id: str):
        """Create a callback for routing sub-agent messages to the parent.

        Args:
            sub_conversation_id: The ID of the sub-agent conversation

        Returns:
            A callback function that processes sub-agent events
        """

        def callback(event):
            """Callback for sub-agent messages - queues them for parent."""
            logger.debug(
                f"Sub-agent {sub_conversation_id[:8]} callback triggered: "
                f"event_type={type(event).__name__}, "
                f"source={getattr(event, 'source', 'N/A')}"
            )

            if not (isinstance(event, MessageEvent) and event.source == "agent"):
                logger.debug(
                    f"Sub-agent {sub_conversation_id[:8]} ignoring non-agent "
                    f"message event"
                )
                return

            if not (hasattr(event, "llm_message") and event.llm_message):
                logger.debug(
                    f"Sub-agent {sub_conversation_id[:8]} event has no llm_message"
                )
                return

            message_parts = []
            for content in event.llm_message.content:
                if isinstance(content, TextContent):
                    message_parts.append(content.text)
                else:
                    message_parts.append(f"[{type(content).__name__}]")

            message_text = " ".join(message_parts)

            if not message_text.strip():
                logger.debug(
                    f"Sub-agent {sub_conversation_id[:8]} sent empty message, ignoring"
                )
                return

            parent_message = f"[Sub-agent {sub_conversation_id[:8]}]: {message_text}"
            logger.info(
                f"🔄 Sub-agent {sub_conversation_id[:8]} sending "
                f"message to parent: {message_text[:100]}..."
            )

            message = Message(
                role="user",
                content=[TextContent(text=parent_message)],
            )
            try:
                self._pending_parent_messages.put_nowait(message)
                queue_size = self._pending_parent_messages.qsize()
                logger.info(
                    f"✅ Queued message from sub-agent "
                    f"{sub_conversation_id[:8]} "
                    f"(queue size: {queue_size})"
                )
                self._trigger_parent_if_idle()
            except queue.Full:
                logger.warning(
                    f"❌ Parent message queue is full, dropping "
                    f"message from sub-agent {sub_conversation_id[:8]}"
                )

        return callback

    def _run_sub_agent(
        self,
        sub_conversation_id: str,
        sub_conversation: "LocalConversation",
        initial_message: str,
        stop_event: threading.Event,
    ):
        """Run a sub-agent in a separate thread.

        Args:
            sub_conversation_id: The ID of the sub-agent conversation
            sub_conversation: The conversation object for the sub-agent
            initial_message: The initial message to send to the sub-agent
            stop_event: Event to signal cancellation
        """
        try:
            with self._lock:
                if sub_conversation_id in self._sub_agents:
                    self._sub_agents[sub_conversation_id].state = SubAgentState.RUNNING

            logger.info(
                f"Sub-agent {sub_conversation_id[:8]} starting with task: "
                f"{initial_message[:100]}..."
            )

            sub_conversation.send_message(initial_message)

            start_time = time.time()
            max_runtime = 300

            while not stop_event.is_set():
                try:
                    if time.time() - start_time > max_runtime:
                        logger.warning(
                            f"Sub-agent {sub_conversation_id[:8]} timed out "
                            f"after {max_runtime}s"
                        )
                        break

                    sub_conversation.run()

                    if hasattr(sub_conversation, "state") and hasattr(
                        sub_conversation.state, "agent_status"
                    ):
                        status = sub_conversation.state.agent_status
                        logger.info(
                            f"Sub-agent {sub_conversation_id[:8]} "
                            f"status: {status} (type: {type(status)})"
                        )

                        if status == AgentExecutionStatus.FINISHED:
                            logger.info(
                                f"Sub-agent {sub_conversation_id[:8]} "
                                f"reached FINISHED state"
                            )
                            break
                        elif status in [
                            AgentExecutionStatus.PAUSED,
                            AgentExecutionStatus.STUCK,
                            AgentExecutionStatus.ERROR,
                        ]:
                            logger.info(
                                f"Sub-agent {sub_conversation_id[:8]} "
                                f"reached terminal state: {status}"
                            )
                            break
                        elif status == AgentExecutionStatus.IDLE:
                            logger.info(
                                f"Sub-agent {sub_conversation_id[:8]} is IDLE"
                                f" - treating as completion"
                            )
                            break
                        elif status == AgentExecutionStatus.RUNNING:
                            logger.info(
                                f"Sub-agent {sub_conversation_id[:8]} still RUNNING"
                            )
                            time.sleep(0.1)
                            continue
                    else:
                        logger.info(
                            f"Sub-agent {sub_conversation_id[:8]} run() "
                            f"completed (no state check available)"
                        )
                        break

                except Exception as e:
                    if stop_event.is_set():
                        logger.info(f"Sub-agent {sub_conversation_id[:8]} cancelled")
                        break
                    raise e

            if not stop_event.is_set():
                logger.info(
                    f"Sub-agent {sub_conversation_id[:8]} completed successfully"
                )
                with self._lock:
                    if sub_conversation_id in self._sub_agents:
                        self._sub_agents[
                            sub_conversation_id
                        ].state = SubAgentState.COMPLETED
                        self._sub_agents[sub_conversation_id].completed_at = time.time()
            else:
                with self._lock:
                    if sub_conversation_id in self._sub_agents:
                        self._sub_agents[
                            sub_conversation_id
                        ].state = SubAgentState.CANCELLED
                        self._sub_agents[sub_conversation_id].completed_at = time.time()

        except Exception as e:
            logger.error(
                f"Sub-agent {sub_conversation_id[:8]} failed: {e}",
                exc_info=True,
            )

            error_message = f"[Sub-agent {sub_conversation_id[:8]} ERROR]: {str(e)}"
            message = Message(
                role="user",
                content=[TextContent(text=error_message)],
            )
            try:
                self._pending_parent_messages.put_nowait(message)
                self._trigger_parent_if_idle()
            except queue.Full:
                logger.warning("Parent message queue is full, dropping error message")

            with self._lock:
                if sub_conversation_id in self._sub_agents:
                    self._sub_agents[sub_conversation_id].state = SubAgentState.FAILED
                    self._sub_agents[sub_conversation_id].error = str(e)
                    self._sub_agents[sub_conversation_id].completed_at = time.time()

    def _spawn_sub_agent(self, action: "DelegateAction") -> "DelegateObservation":
        """Spawn a new sub-agent that runs asynchronously."""
        if not action.message:
            return DelegateObservation(
                operation="spawn",
                success=False,
                message="Message is required for spawn operation",
            )

        try:
            with self._lock:
                parent_conversation = self.parent_conversation

                active_count = sum(
                    1
                    for sub_agent in self._sub_agents.values()
                    if sub_agent.state in (SubAgentState.CREATED, SubAgentState.RUNNING)
                )
                if active_count >= self._max_children:
                    return DelegateObservation(
                        operation="spawn",
                        success=False,
                        message=(
                            f"Maximum number of sub-agents ({self._max_children}) "
                            "reached"
                        ),
                    )

            parent_llm = parent_conversation.agent.llm
            worker_agent = get_default_agent(
                llm=parent_llm.model_copy(update={"service_id": "sub_agent"}),
            )
            visualize = getattr(parent_conversation, "visualize", True)
            workspace_path = parent_conversation.state.workspace.working_dir

            sub_conversation_id = str(uuid.uuid4())
            stop_event = threading.Event()

            callback = self._create_sub_agent_callback(sub_conversation_id)

            sub_conversation = LocalConversation(
                agent=worker_agent,
                workspace=workspace_path,
                visualize=visualize,
                callbacks=[callback],
                conversation_id=sub_conversation_id,
            )

            thread = threading.Thread(
                target=self._run_sub_agent,
                args=(
                    sub_conversation_id,
                    sub_conversation,
                    action.message,
                    stop_event,
                ),
                name=f"SubAgent-{sub_conversation_id[:8]}",
                daemon=True,
            )

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
        if not action.sub_conversation_id:
            return DelegateObservation(
                operation="close",
                success=False,
                message="Sub-conversation ID is required for close operation",
            )

        with self._lock:
            sub_agent = self._sub_agents.get(action.sub_conversation_id)
            if sub_agent is None:
                # Sub-agent might have been auto-cleaned up already
                logger.info(
                    f"Sub-agent {action.sub_conversation_id[:8]} not found - "
                    f"likely already cleaned up"
                )
                return DelegateObservation(
                    operation="close",
                    success=True,
                    sub_conversation_id=action.sub_conversation_id,
                    message=(
                        f"Sub-agent {action.sub_conversation_id} already cleaned up "
                        f"or completed"
                    ),
                )

        try:
            return self._cancel_sub_agent(action.sub_conversation_id)
        except Exception as e:
            logger.error(f"Failed to close sub-agent {action.sub_conversation_id}: {e}")
            return DelegateObservation(
                operation="close",
                success=False,
                sub_conversation_id=action.sub_conversation_id,
                message=f"Failed to close sub-agent {action.sub_conversation_id}: {e}",
            )

    def _cancel_sub_agent(self, sub_conversation_id: str) -> "DelegateObservation":
        """Cancel a sub-agent with proper thread joining outside lock."""
        # Get sub-agent info and signal stop under lock
        with self._lock:
            sub_agent = self._sub_agents.get(sub_conversation_id)
            if sub_agent is None:
                # Sub-agent might have been auto-cleaned up already
                logger.info(
                    f"Sub-agent {sub_conversation_id[:8]} not found - "
                    f"likely already cleaned up"
                )
                return DelegateObservation(
                    operation="close",
                    success=True,
                    sub_conversation_id=sub_conversation_id,
                    message=(
                        f"Sub-agent {sub_conversation_id} already cleaned up "
                        f"or completed"
                    ),
                )

            # Signal the sub-agent to stop and update state
            sub_agent.stop_event.set()
            sub_agent.state = SubAgentState.CANCELLED
            sub_agent.completed_at = time.time()

            # Note: Callbacks cannot be detached from LocalConversation after creation
            # The sub-agent will stop generating events when the thread terminates

            thread = sub_agent.thread

        # Wait for thread to finish outside of lock
        if thread.is_alive():
            logger.info(f"Waiting for sub-agent {sub_conversation_id[:8]} to stop...")
            try:
                # Check if we're trying to join the current thread
                current_thread = threading.current_thread()
                if thread == current_thread:
                    logger.warning(
                        f"Cannot join current thread for sub-agent "
                        f"{sub_conversation_id[:8]} - thread will terminate naturally"
                    )
                else:
                    thread.join(timeout=10.0)
                    if thread.is_alive():
                        logger.warning(
                            f"Sub-agent {sub_conversation_id[:8]} did not stop "
                            f"gracefully within timeout"
                        )
            except RuntimeError as e:
                # Handle "cannot join current thread" and other threading errors
                logger.info(
                    f"Thread join not possible for sub-agent "
                    f"{sub_conversation_id[:8]}: {e} - thread will terminate naturally"
                )

        logger.info(f"Closed sub-agent {sub_conversation_id[:8]}")

        return DelegateObservation(
            operation="close",
            success=True,
            sub_conversation_id=sub_conversation_id,
            message=f"Sub-agent {sub_conversation_id} closed successfully",
        )

    def _cancel_sub_agent_unsafe(
        self, sub_conversation_id: str
    ) -> "DelegateObservation":
        """Cancel a sub-agent. Must be called with lock held.

        DEPRECATED - use _cancel_sub_agent instead.
        """
        # For backward compatibility, check if lock is held and handle appropriately
        lock_was_held = self._lock._count > 0  # Check if RLock is held
        if lock_was_held:
            # Release lock and call the safe version
            self._lock.release()
            try:
                return self._cancel_sub_agent(sub_conversation_id)
            finally:
                self._lock.acquire()
        else:
            # Lock not held, just call the safe version directly
            return self._cancel_sub_agent(sub_conversation_id)
