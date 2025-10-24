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


class SubAgentInfo(BaseModel):
    """Information about a sub-agent."""

    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)

    conversation_id: str
    conversation: Any  # BaseConversation - using Any to avoid forward reference issues
    thread: Any  # threading.Thread - using Any for runtime objects
    state: SubAgentState
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

    def __init__(self, max_children: int = 5):
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

    def is_task_in_progress(self) -> bool:
        """Check if a task started by the parent conversation is still in progress."""
        with self._lock:
            parent_running = (
                self.parent_conversation.state.agent_status
                != AgentExecutionStatus.FINISHED
            )

            pending_messages = self._pending_parent_messages.qsize() > 0

            active_sub_agents = any(
                sub_agent.state in (SubAgentState.CREATED, SubAgentState.RUNNING)
                for sub_agent in self._sub_agents.values()
            )

            return parent_running or pending_messages or active_sub_agents

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

        return self._delegate_task(action)

    def _trigger_parent_if_idle(self):
        """
        Core rule: If parent.state.agent_status == FINISHED and there are pending
        child outputs queued for the parent, then trigger exactly one
        parent_conversation.run().

        This provides:
        - No re-entrancy: only fire when parent is idle
        - Natural batching: all messages that arrive while parent is busy are
          processed together
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
        sub_conversation: "LocalConversation",
        initial_message: str,
    ):
        """Run a sub-agent in a separate thread.

        Args:
            sub_conversation_id: The ID of the sub-agent conversation
            sub_conversation: The conversation object for the sub-agent
            initial_message: The initial message to send to the sub-agent
        """
        sub_conversation_id = str(sub_conversation.id)
        try:
            with self._lock:
                if sub_conversation_id in self._sub_agents:
                    self._sub_agents[sub_conversation_id].state = SubAgentState.RUNNING

            logger.info(
                f"Sub-agent {sub_conversation_id[:8]} starting with task: "
                f"{initial_message[:100]}..."
            )

            sub_conversation.send_message(initial_message)
            sub_conversation.run()

            logger.info(f"Sub-agent {sub_conversation_id[:8]} completed")

            with self._lock:
                if sub_conversation_id in self._sub_agents:
                    self._sub_agents[
                        sub_conversation_id
                    ].state = SubAgentState.COMPLETED
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

    def _delegate_task(self, action: "DelegateAction") -> "DelegateObservation":
        """Delegate a task to a new sub-agent that runs asynchronously."""
        if not action.task:
            return DelegateObservation(
                success=False,
                message="Task is required for delegate action",
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
                    sub_conversation,
                    action.task,
                ),
                name=f"SubAgent-{sub_conversation_id[:8]}",
                daemon=True,
            )

            sub_agent_info = SubAgentInfo(
                conversation_id=sub_conversation_id,
                conversation=sub_conversation,
                thread=thread,
                state=SubAgentState.CREATED,
                created_at=time.time(),
            )

            with self._lock:
                self._sub_agents[sub_conversation_id] = sub_agent_info

            thread.start()

            logger.info(
                f"Delegated task to sub-agent {sub_conversation_id[:8]}: "
                f"{action.task[:100]}..."
            )

            return DelegateObservation(
                success=True,
                sub_conversation_id=sub_conversation_id,
                message=(
                    f"Sub-agent {sub_conversation_id} created and running "
                    "asynchronously"
                ),
            )

        except Exception as e:
            logger.error(f"Failed to delegate task: {e}", exc_info=True)
            return DelegateObservation(
                success=False,
                message=f"Failed to delegate task: {str(e)}",
            )
