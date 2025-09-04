from typing import TYPE_CHECKING, Iterable


if TYPE_CHECKING:
    from openhands.sdk.agent import AgentBase

from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.conversation.types import ConversationCallbackType
from openhands.sdk.conversation.visualizer import ConversationVisualizer
from openhands.sdk.event import (
    ActionEvent,
    MessageEvent,
    UserRejectsObservation,
)
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
        agent: "AgentBase",
        callbacks: list[ConversationCallbackType] | None = None,
        max_iteration_per_run: int = 500,
    ):
        """Initialize the conversation."""
        self._visualizer = ConversationVisualizer()
        self.agent = agent
        self.state = ConversationState()

        # Default callback: persist every event to state
        def _append_event(e):
            self.state.events.append(e)

        # Compose callbacks; default appender runs last to keep agent-emitted event order (on_event then persist)  # noqa: E501
        composed_list = (
            [self._visualizer.on_event]
            + (callbacks if callbacks else [])
            + [_append_event]
        )
        self._on_event = compose_callbacks(composed_list)

        self.max_iteration_per_run = max_iteration_per_run

        with self.state:
            self.agent.init_state(self.state, on_event=self._on_event)

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
        """
        iteration = 0
        while not self.state.agent_finished:
            logger.debug(f"Conversation run iteration {iteration}")
            # TODO(openhands): we should add a testcase that test IF:
            # 1. a loop is running
            # 2. in a separate thread .send_message is called
            # and check will we be able to execute .send_message
            # BEFORE the .run loop finishes?
            with self.state:
                # clear the flag before calling agent.step() (user approved)
                if self.state.waiting_for_confirmation:
                    self.state.waiting_for_confirmation = False

                # step must mutate the SAME state object
                self.agent.step(self.state, on_event=self._on_event)

            # In confirmation mode, stop after one iteration if waiting for confirmation
            if self.state.waiting_for_confirmation:
                break

            iteration += 1
            if iteration >= self.max_iteration_per_run:
                break

    def get_pending_actions(self) -> list[ActionEvent]:
        """Get all actions that are waiting for confirmation from the agent."""
        return self.agent.get_pending_actions(self.state)

    def set_confirmation_mode(self, enabled: bool) -> None:
        """Enable or disable confirmation mode and store it in conversation state."""
        with self.state:
            self.state.confirmation_mode = enabled
        logger.info(f"Confirmation mode {'enabled' if enabled else 'disabled'}")

    def reject_pending_actions(self, reason: str = "User rejected the action") -> None:
        """Reject all pending actions from the agent.

        This is a non-invasive method to reject actions between run() calls.
        Also clears the waiting_for_confirmation flag.
        """
        pending_actions = self.agent.get_pending_actions(self.state)

        with self.state:
            # Always clear the waiting_for_confirmation flag
            self.state.waiting_for_confirmation = False

            if not pending_actions:
                logger.warning("No pending actions to reject")
                return

            for action_event in pending_actions:
                # Create rejection observation
                rejection_event = UserRejectsObservation(
                    action_id=action_event.id,
                    tool_name=action_event.tool_name,
                    tool_call_id=action_event.tool_call_id,
                    rejection_reason=reason,
                )
                self._on_event(rejection_event)
                logger.info(f"Rejected pending action: {action_event} - {reason}")
