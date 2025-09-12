import uuid
from typing import TYPE_CHECKING, Iterable


if TYPE_CHECKING:
    from openhands.sdk.agent import AgentType

from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.conversation.types import ConversationCallbackType
from openhands.sdk.conversation.visualizer import (
    create_default_visualizer,
)
from openhands.sdk.event import (
    MessageEvent,
    PauseEvent,
    UserRejectObservation,
)
from openhands.sdk.event.utils import get_unmatched_actions
from openhands.sdk.io import FileStore
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


def compose_callbacks(
    callbacks: Iterable[ConversationCallbackType],
) -> ConversationCallbackType:
    def composed(event) -> None:
        for cb in callbacks:
            if cb:
                cb(event)

    return composed


class Conversation:
    def __init__(
        self,
        agent: "AgentType",
        persist_filestore: FileStore | None = None,
        conversation_id: str | None = None,
        callbacks: list[ConversationCallbackType] | None = None,
        max_iteration_per_run: int = 500,
        visualize: bool = True,
    ):
        """Initialize the conversation.

        Args:
            agent: The agent to use for the conversation
            persist_filestore: Optional FileStore to persist conversation state
            conversation_id: Optional ID for the conversation. If provided, will
                      be used to identify the conversation. The user might want to
                      suffix their persistent filestore with this ID.
            callbacks: Optional list of callback functions to handle events
            max_iteration_per_run: Maximum number of iterations per run
            visualize: Whether to enable default visualization. If True, adds
                      a default visualizer callback. If False, relies on
                      application to provide visualization through callbacks.
        """
        self.agent = agent
        self._persist_filestore = persist_filestore

        # Create-or-resume: factory inspects BASE_STATE to decide
        desired_id = conversation_id or str(uuid.uuid4())
        self.state = ConversationState.create(
            id=desired_id,
            agent=agent,
            file_store=self._persist_filestore,
        )

        # Default callback: persist every event to state
        def _default_callback(e):
            self.state.events.append(e)

        composed_list = (callbacks if callbacks else []) + [_default_callback]
        # Add default visualizer if requested
        if visualize:
            self._visualizer = create_default_visualizer()
            composed_list = [self._visualizer.on_event] + composed_list
            # visualize should happen first for visibility
        else:
            self._visualizer = None

        self._on_event = compose_callbacks(composed_list)
        self.max_iteration_per_run = max_iteration_per_run

        with self.state:
            self.agent.init_state(self.state, on_event=self._on_event)

    @property
    def id(self) -> str:
        """Get the unique ID of the conversation."""
        return self.state.id

    def send_message(self, message: Message) -> None:
        """Sending messages to the agent."""
        assert message.role == "user", (
            "Only user messages are allowed to be sent to the agent."
        )
        with self.state:
            if self.state.agent_finished:
                self.state.agent_finished = False  # now we have a new message

            # TODO: We should add test cases for all these scenarios
            activated_microagent_names: list[str] = []
            extended_content: list[TextContent] = []

            # Handle per-turn user message (i.e., knowledge agent trigger)
            if self.agent.agent_context:
                ctx = self.agent.agent_context.get_user_message_suffix(
                    user_message=message,
                    # We skip microagents that were already activated
                    skip_microagent_names=self.state.activated_knowledge_microagents,
                )
                # TODO(calvin): we need to update
                # self.state.activated_knowledge_microagents
                # so condenser can work
                if ctx:
                    content, activated_microagent_names = ctx
                    logger.debug(
                        f"Got augmented user message content: {content}, "
                        f"activated microagents: {activated_microagent_names}"
                    )
                    extended_content.append(content)
                    self.state.activated_knowledge_microagents.extend(
                        activated_microagent_names
                    )

            user_msg_event = MessageEvent(
                source="user",
                llm_message=message,
                activated_microagents=activated_microagent_names,
                extended_content=extended_content,
            )
            self._on_event(user_msg_event)

    def run(self) -> None:
        """Runs the conversation until the agent finishes.

        In confirmation mode:
        - First call: creates actions but doesn't execute them, stops and waits
        - Second call: executes pending actions (implicit confirmation)

        In normal mode:
        - Creates and executes actions immediately

        Can be paused between steps
        """

        with self.state:
            self.state.agent_paused = False

        iteration = 0
        while True:
            logger.debug(f"Conversation run iteration {iteration}")
            # TODO(openhands): we should add a testcase that test IF:
            # 1. a loop is running
            # 2. in a separate thread .send_message is called
            # and check will we be able to execute .send_message
            # BEFORE the .run loop finishes?
            with self.state:
                # Pause attempts to acquire the state lock
                # Before value can be modified step can be taken
                # Ensure step conditions are checked when lock is already acquired
                if self.state.agent_finished or self.state.agent_paused:
                    break

                # clear the flag before calling agent.step() (user approved)
                if self.state.agent_waiting_for_confirmation:
                    self.state.agent_waiting_for_confirmation = False

                # step must mutate the SAME state object
                self.agent.step(self.state, on_event=self._on_event)

            # In confirmation mode, stop after one iteration if waiting for confirmation
            if self.state.agent_waiting_for_confirmation:
                break

            iteration += 1
            if iteration >= self.max_iteration_per_run:
                break

    def set_confirmation_mode(self, enabled: bool) -> None:
        """Enable or disable confirmation mode and store it in conversation state."""
        with self.state:
            self.state.confirmation_mode = enabled
        logger.info(f"Confirmation mode {'enabled' if enabled else 'disabled'}")

    def reject_pending_actions(self, reason: str = "User rejected the action") -> None:
        """Reject all pending actions from the agent.

        This is a non-invasive method to reject actions between run() calls.
        Also clears the agent_waiting_for_confirmation flag.
        """
        pending_actions = get_unmatched_actions(self.state.events)

        with self.state:
            # Always clear the agent_waiting_for_confirmation flag
            self.state.agent_waiting_for_confirmation = False

            if not pending_actions:
                logger.warning("No pending actions to reject")
                return

            for action_event in pending_actions:
                # Create rejection observation
                rejection_event = UserRejectObservation(
                    action_id=action_event.id,
                    tool_name=action_event.tool_name,
                    tool_call_id=action_event.tool_call_id,
                    rejection_reason=reason,
                )
                self._on_event(rejection_event)
                logger.info(f"Rejected pending action: {action_event} - {reason}")

    def pause(self) -> None:
        """Pause agent execution.

        This method can be called from any thread to request that the agent
        pause execution. The pause will take effect at the next iteration
        of the run loop (between agent steps).

        Note: If called during an LLM completion, the pause will not take
        effect until the current LLM call completes.
        """

        if self.state.agent_paused:
            return

        with self.state:
            self.state.agent_paused = True
            pause_event = PauseEvent()
            self._on_event(pause_event)
        logger.info("Agent execution pause requested")

    def close(self) -> None:
        """Close the conversation and clean up all tool executors."""
        logger.debug("Closing conversation and cleaning up tool executors")
        assert isinstance(self.agent.tools, dict), "Agent tools should be a dict"
        for tool in self.agent.tools.values():
            if tool.executor is not None:
                try:
                    tool.executor.close()
                except Exception as e:
                    logger.warning(
                        f"Error closing executor for tool '{tool.name}': {e}"
                    )

    def __del__(self) -> None:
        """Ensure cleanup happens when conversation is destroyed."""
        try:
            self.close()
        except Exception as e:
            logger.warning(f"Error during conversation cleanup: {e}", exc_info=True)
