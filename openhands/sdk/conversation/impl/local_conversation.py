import uuid
from typing import Iterable

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation.base import BaseConversation
from openhands.sdk.conversation.secrets_manager import SecretValue
from openhands.sdk.conversation.state import AgentExecutionStatus, ConversationState
from openhands.sdk.conversation.stuck_detector import StuckDetector
from openhands.sdk.conversation.types import ConversationCallbackType, ConversationID
from openhands.sdk.conversation.visualizer import create_default_visualizer
from openhands.sdk.event import (
    MessageEvent,
    PauseEvent,
    UserRejectObservation,
)
from openhands.sdk.event.utils import get_unmatched_actions
from openhands.sdk.io import FileStore
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.security.confirmation_policy import (
    ConfirmationPolicyBase,
    NeverConfirm,
)


logger = get_logger(__name__)


def compose_callbacks(
    callbacks: Iterable[ConversationCallbackType],
) -> ConversationCallbackType:
    def composed(event) -> None:
        for cb in callbacks:
            if cb:
                cb(event)

    return composed


class LocalConversation(BaseConversation):
    def __init__(
        self,
        agent: AgentBase,
        persist_filestore: FileStore | None = None,
        conversation_id: ConversationID | None = None,
        callbacks: list[ConversationCallbackType] | None = None,
        max_iteration_per_run: int = 500,
        stuck_detection: bool = True,
        visualize: bool = True,
        **_: object,
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
            stuck_detection: Whether to enable stuck detection
        """
        self.agent = agent
        self._persist_filestore = persist_filestore

        # Create-or-resume: factory inspects BASE_STATE to decide
        desired_id = conversation_id or uuid.uuid4()
        self._state = ConversationState.create(
            id=desired_id,
            agent=agent,
            file_store=self._persist_filestore,
            max_iterations=max_iteration_per_run,
            stuck_detection=stuck_detection,
        )

        # Default callback: persist every event to state
        def _default_callback(e):
            self._state.events.append(e)

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

        # Initialize stuck detector
        self._stuck_detector = StuckDetector(self._state) if stuck_detection else None

        with self._state:
            self.agent.init_state(self._state, on_event=self._on_event)

    @property
    def id(self) -> ConversationID:
        """Get the unique ID of the conversation."""
        return self._state.id

    @property
    def state(self) -> ConversationState:
        """Get the conversation state.

        It returns a protocol that has a subset of ConversationState methods
        and properties. We will have the ability to access the same properties
        of ConversationState on a remote conversation object.
        But we won't be able to access methods that mutate the state.
        """
        return self._state

    @property
    def stuck_detector(self) -> StuckDetector | None:
        """Get the stuck detector instance if enabled."""
        return self._stuck_detector

    def send_message(self, message: str | Message) -> None:
        """Send a message to the agent.

        Args:
            message: Either a string (which will be converted to a user message)
                    or a Message object
        """
        # Convert string to Message if needed
        if isinstance(message, str):
            message = Message(role="user", content=[TextContent(text=message)])

        assert message.role == "user", (
            "Only user messages are allowed to be sent to the agent."
        )
        with self._state:
            if self._state.agent_status == AgentExecutionStatus.FINISHED:
                self._state.agent_status = (
                    AgentExecutionStatus.IDLE
                )  # now we have a new message

            # TODO: We should add test cases for all these scenarios
            activated_microagent_names: list[str] = []
            extended_content: list[TextContent] = []

            # Handle per-turn user message (i.e., knowledge agent trigger)
            if self.agent.agent_context:
                ctx = self.agent.agent_context.get_user_message_suffix(
                    user_message=message,
                    # We skip microagents that were already activated
                    skip_microagent_names=self._state.activated_knowledge_microagents,
                )
                # TODO(calvin): we need to update
                # self._state.activated_knowledge_microagents
                # so condenser can work
                if ctx:
                    content, activated_microagent_names = ctx
                    logger.debug(
                        f"Got augmented user message content: {content}, "
                        f"activated microagents: {activated_microagent_names}"
                    )
                    extended_content.append(content)
                    self._state.activated_knowledge_microagents.extend(
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

        with self._state:
            if self._state.agent_status == AgentExecutionStatus.PAUSED:
                self._state.agent_status = AgentExecutionStatus.RUNNING

        iteration = 0
        while True:
            logger.debug(f"Conversation run iteration {iteration}")
            with self._state:
                # Pause attempts to acquire the state lock
                # Before value can be modified step can be taken
                # Ensure step conditions are checked when lock is already acquired
                if self._state.agent_status in [
                    AgentExecutionStatus.FINISHED,
                    AgentExecutionStatus.PAUSED,
                    AgentExecutionStatus.STUCK,
                ]:
                    break

                # Check for stuck patterns if enabled
                if self._stuck_detector:
                    is_stuck = self._stuck_detector.is_stuck()

                    if is_stuck:
                        logger.warning("Stuck pattern detected.")
                        self._state.agent_status = AgentExecutionStatus.STUCK
                        continue

                # clear the flag before calling agent.step() (user approved)
                if (
                    self._state.agent_status
                    == AgentExecutionStatus.WAITING_FOR_CONFIRMATION
                ):
                    self._state.agent_status = AgentExecutionStatus.RUNNING

                # step must mutate the SAME state object
                self.agent.step(self._state, on_event=self._on_event)
                iteration += 1

                if (
                    self.state.agent_status == AgentExecutionStatus.FINISHED
                    or self.state.agent_status
                    == AgentExecutionStatus.WAITING_FOR_CONFIRMATION
                    or iteration >= self.max_iteration_per_run
                ):
                    break

    def set_confirmation_policy(self, policy: ConfirmationPolicyBase) -> None:
        """Set the confirmation policy and store it in conversation state."""
        with self._state:
            self._state.confirmation_policy = policy
        logger.info(f"Confirmation policy set to: {policy}")

    @property
    def confirmation_policy_active(self) -> bool:
        return not isinstance(self.state.confirmation_policy, NeverConfirm)

    def reject_pending_actions(self, reason: str = "User rejected the action") -> None:
        """Reject all pending actions from the agent.

        This is a non-invasive method to reject actions between run() calls.
        Also clears the agent_waiting_for_confirmation flag.
        """
        pending_actions = get_unmatched_actions(self._state.events)

        with self._state:
            # Always clear the agent_waiting_for_confirmation flag
            if (
                self._state.agent_status
                == AgentExecutionStatus.WAITING_FOR_CONFIRMATION
            ):
                self._state.agent_status = AgentExecutionStatus.IDLE

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

        if self._state.agent_status == AgentExecutionStatus.PAUSED:
            return

        with self._state:
            # Only pause when running or idle
            if (
                self._state.agent_status == AgentExecutionStatus.IDLE
                or self._state.agent_status == AgentExecutionStatus.RUNNING
            ):
                self._state.agent_status = AgentExecutionStatus.PAUSED
                pause_event = PauseEvent()
                self._on_event(pause_event)
                logger.info("Agent execution pause requested")

    def update_secrets(self, secrets: dict[str, SecretValue]) -> None:
        """Add secrets to the conversation.

        Args:
            secrets: Dictionary mapping secret keys to values or no-arg callables.
                     SecretValue = str | Callable[[], str]. Callables are invoked lazily
                     when a command references the secret key.
        """

        secrets_manager = self._state.secrets_manager
        secrets_manager.update_secrets(secrets)
        logger.info(f"Added {len(secrets)} secrets to conversation")

    def close(self) -> None:
        """Close the conversation and clean up all tool executors."""
        logger.debug("Closing conversation and cleaning up tool executors")
        for tool in self.agent.tools_map.values():
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
