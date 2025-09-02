from typing import TYPE_CHECKING, Iterable


if TYPE_CHECKING:
    from openhands.core.agent import AgentBase

from openhands.core.event import MessageEvent
from openhands.core.llm import Message, TextContent
from openhands.core.logger import get_logger

from .state import ConversationState
from .types import ConversationCallbackType
from .visualizer import ConversationVisualizer


logger = get_logger(__name__)


def compose_callbacks(callbacks: Iterable[ConversationCallbackType]) -> ConversationCallbackType:
    def composed(event) -> None:
        for cb in callbacks:
            if cb:
                cb(event)

    return composed


class Conversation:
    def __init__(self, agent: "AgentBase", callbacks: list[ConversationCallbackType] | None = None, max_iteration_per_run: int = 500):
        """Initialize the conversation."""
        self._visualizer = ConversationVisualizer()
        self.agent = agent
        self.state = ConversationState()

        # Default callback: persist every event to state
        def _append_event(e):
            self.state.events.append(e)

        # Compose callbacks; default appender runs last to keep agent-emitted event order (on_event then persist)
        composed_list = [self._visualizer.on_event] + (callbacks if callbacks else []) + [_append_event]
        self._on_event = compose_callbacks(composed_list)

        self.max_iteration_per_run = max_iteration_per_run

        with self.state:
            self.agent.init_state(self.state, on_event=self._on_event)


    def send_message(self, message: Message) -> None:
        """Sending messages to the agent."""
        assert message.role == "user", "Only user messages are allowed to be sent to the agent."
        with self.state:
            if self.state.agent_finished:
                self.state.agent_finished = False  # now we have a new message

            # TODO: We should add test cases for all these scenarios
            activated_microagent_names: list[str] = []
            extended_content: list[TextContent] = []
            
            # 1) Handle initial message
            if not self.state.initial_message_sent:
                if self.agent.agent_context:
                    initial_env_context: TextContent | None = self.agent.agent_context.render_environment_context(self.agent.prompt_dir)
                    logger.debug(f"Got initial environment context: {initial_env_context}")
                    if initial_env_context:
                        extended_content.append(initial_env_context)
                self.state.initial_message_sent = True

            # 2) Handle per-turn user message (i.e., knowledge agent trigger)
            if self.agent.agent_context:
                augmented = self.agent.agent_context.augment_user_message_with_knowledge(
                    prompt_dir=self.agent.prompt_dir,
                    user_message=message,
                    # We skip microagents that were already activated
                    skip_microagent_names=self.state.activated_knowledge_microagents
                )
                # TODO(calvin): we need to update self.state.activated_knowledge_microagents
                # so condenser can work
                if augmented:
                    content, activated_microagent_names = augmented
                    logger.debug(f"Got augmented user message content: {content}, activated microagents: {activated_microagent_names}")
                    extended_content.append(content)
                    self.state.activated_knowledge_microagents.extend(activated_microagent_names)
    
            user_msg_event = MessageEvent(
                source="user",
                llm_message=message,
                activated_microagents=activated_microagent_names,
                extended_content=extended_content
            )
            self._on_event(user_msg_event)

    def run(self) -> None:
        """Runs the conversation until the agent finishes."""
        iteration = 0
        while not self.state.agent_finished:
            logger.debug(f"Conversation run iteration {iteration}")
            # TODO(openhands): we should add a testcase that test IF:
            # 1. a loop is running
            # 2. in a separate thread .send_message is called
            # and check will we be able to execute .send_message
            # BEFORE the .run loop finishes?
            with self.state:
                # step must mutate the SAME state object
                self.agent.step(self.state, on_event=self._on_event)
            iteration += 1
            if iteration >= self.max_iteration_per_run:
                break
