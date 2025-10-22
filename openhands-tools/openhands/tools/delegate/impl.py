"""Implementation of delegate tool executor."""

import threading
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


class DelegateExecutor(ToolExecutor):
    """Executor for delegation operations.

    This class handles:
    - Creating sub-agents and their conversations
    - Tracking parent-child relationships in memory
    - Routing messages between parent and child agents
    - Managing sub-agent lifecycle
    """

    def __init__(self):
        self.conversations: dict[str, BaseConversation] = {}
        self.child_to_parent: dict[str, str] = {}
        self.sub_agent_threads: dict[str, threading.Thread] = {}
        self.parent_threads: dict[str, list[threading.Thread]] = {}

    def register_conversation(self, conversation: "BaseConversation") -> None:
        """Register a conversation with the delegation executor."""
        self.conversations[str(conversation.id)] = conversation
        logger.debug(f"Registered conversation {conversation.id}")

    def get_conversation(self, conversation_id: str) -> "BaseConversation | None":
        """Get a conversation by ID."""
        return self.conversations.get(conversation_id)

    def is_task_in_progress(self, conversation_id: str) -> bool:
        """Check if a task started by a parent conversation is still in progress."""
        linked_sub_conversation_ids = []
        for sub_conv_id, parent_id in self.child_to_parent.items():
            if parent_id == conversation_id:
                linked_sub_conversation_ids.append(sub_conv_id)

        for sub_conv_id in linked_sub_conversation_ids:
            thread = self.sub_agent_threads.get(sub_conv_id)
            if thread and thread.is_alive():
                logger.debug(f"Sub-agent {sub_conv_id[:8]} thread still active")
                return True

        parent_threads = self.parent_threads.get(conversation_id, [])
        for thread in parent_threads:
            if thread.is_alive():
                logger.debug("Parent conversation thread still active")
                return True

        return False

    def __call__(self, action: "DelegateAction", conversation) -> "DelegateObservation":
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

    def _spawn_sub_agent(
        self, action: "DelegateAction", conversation: "BaseConversation"
    ) -> "DelegateObservation":
        """Spawn a new sub-agent that runs asynchronously."""
        from openhands.tools.delegate.definition import DelegateObservation

        if not action.task:
            return DelegateObservation(
                operation="spawn",
                success=False,
                message="Task is required for spawn operation",
            )

        try:
            conversation_id = str(conversation.id)
            parent_conversation = self.get_conversation(conversation_id)
            if parent_conversation is None:
                self.register_conversation(conversation)
                parent_conversation = conversation

            from openhands.tools.preset.default import get_default_agent

            parent_llm = parent_conversation.agent.llm  # type: ignore[attr-defined]
            cli_mode = getattr(
                parent_conversation.agent,  # type: ignore[attr-defined]
                "cli_mode",
                False,
            ) or not hasattr(parent_conversation, "workspace")

            worker_agent = get_default_agent(
                llm=parent_llm.model_copy(update={"service_id": "sub_agent"}),
                cli_mode=cli_mode,
                enable_delegation=False,
            )

            visualize = getattr(parent_conversation, "visualize", True)

            sub_conversation_id_holder: list[str | None] = [None]

            def sub_agent_completion_callback(event):
                if isinstance(event, MessageEvent) and event.source == "agent":
                    if hasattr(event, "llm_message") and event.llm_message:
                        message_text = ""
                        for content in event.llm_message.content:
                            if isinstance(content, TextContent):
                                message_text += content.text

                        sub_id = sub_conversation_id_holder[0]
                        if sub_id is None:
                            logger.error("Sub-conversation ID not set in callback")
                            return

                        parent_message = f"[Sub-agent {sub_id[:8]}]: {message_text}"
                        logger.info(
                            f"Sub-agent {sub_id[:8]} sending message "
                            f"to parent: {message_text[:100]}..."
                        )
                        parent_conversation.send_message(
                            Message(
                                role="user",
                                content=[TextContent(text=parent_message)],
                            )
                        )

                        def run_parent():
                            try:
                                logger.info(
                                    f"Sub-agent {sub_id[:8]} triggering "
                                    "parent conversation to run"
                                )
                                parent_conversation.run()
                            except Exception as e:
                                logger.error(
                                    (
                                        "Error running parent conversation "
                                        "from sub-agent: %s"
                                    ),
                                    e,
                                    exc_info=True,
                                )

                        parent_thread = threading.Thread(
                            target=run_parent, daemon=False
                        )
                        parent_thread.start()

                        parent_id = str(parent_conversation.id)
                        if parent_id not in self.parent_threads:
                            self.parent_threads[parent_id] = []
                        self.parent_threads[parent_id].append(parent_thread)

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

            sub_conversation_id = str(sub_conversation.id)
            sub_conversation_id_holder[0] = sub_conversation_id

            self.conversations[sub_conversation_id] = sub_conversation

            parent_id = str(parent_conversation.id)
            self.child_to_parent[sub_conversation_id] = parent_id

            def run_sub_agent():
                try:
                    # action.task is guaranteed to be not None due to check at line 93
                    assert action.task is not None
                    logger.info(
                        f"Sub-agent {sub_conversation_id[:8]} starting with task: "
                        f"{action.task[:100]}..."
                    )
                    sub_conversation.send_message(action.task)
                    sub_conversation.run()
                    logger.info(f"Sub-agent {sub_conversation_id[:8]} completed")
                except Exception as e:
                    logger.error(
                        f"Sub-agent {sub_conversation_id[:8]} failed: {e}",
                        exc_info=True,
                    )
                    parent_conversation.send_message(
                        Message(
                            role="user",
                            content=[
                                TextContent(
                                    text=(
                                        f"[Sub-agent {sub_conversation_id[:8]} ERROR]: "
                                        f"{str(e)}"
                                    )
                                )
                            ],
                        )
                    )

            thread = threading.Thread(target=run_sub_agent, daemon=False)
            self.sub_agent_threads[sub_conversation_id] = thread
            thread.start()

            # action.task is guaranteed to be not None due to check at line 93
            assert action.task is not None
            logger.info(
                f"Spawned sub-agent {sub_conversation_id[:8]} with task: "
                f"{action.task[:100]}..."
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

        sub_conversation = self.conversations.get(action.sub_conversation_id)
        if sub_conversation is None:
            logger.error(f"Sub-conversation {action.sub_conversation_id} not found")
            return DelegateObservation(
                operation="send",
                success=False,
                sub_conversation_id=action.sub_conversation_id,
                message=(
                    f"Failed to send message to sub-agent {action.sub_conversation_id}"
                ),
            )

        try:
            sub_conversation.send_message(action.message)
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
                    f"Failed to send message to sub-agent {action.sub_conversation_id}"
                ),
            )

    def _close_sub_agent(self, action: "DelegateAction") -> "DelegateObservation":
        """Close a sub-agent."""
        from openhands.tools.delegate.definition import DelegateObservation

        if not action.sub_conversation_id:
            return DelegateObservation(
                operation="close",
                success=False,
                message="Sub-conversation ID is required for close operation",
            )

        if action.sub_conversation_id not in self.conversations:
            logger.error(f"Sub-conversation {action.sub_conversation_id} not found")
            return DelegateObservation(
                operation="close",
                success=False,
                sub_conversation_id=action.sub_conversation_id,
                message=f"Failed to close sub-agent {action.sub_conversation_id}",
            )

        try:
            if action.sub_conversation_id in self.child_to_parent:
                del self.child_to_parent[action.sub_conversation_id]

            del self.conversations[action.sub_conversation_id]

            logger.info(f"Closed sub-agent {action.sub_conversation_id}")
            return DelegateObservation(
                operation="close",
                success=True,
                sub_conversation_id=action.sub_conversation_id,
                message=f"Sub-agent {action.sub_conversation_id} closed successfully",
            )
        except Exception as e:
            logger.error(f"Failed to close sub-agent {action.sub_conversation_id}: {e}")
            return DelegateObservation(
                operation="close",
                success=False,
                sub_conversation_id=action.sub_conversation_id,
                message=f"Failed to close sub-agent {action.sub_conversation_id}",
            )
