"""Test for examples/example_01_hello_world.py using the suggested testing patterns."""

from pydantic import SecretStr

from examples.ex_01_hello_world import example
from openhands.sdk import LLM, AgentBase
from openhands.sdk.conversation import ConversationCallbackType, ConversationState
from openhands.sdk.conversation.state import AgentExecutionStatus


class FakeAgent(AgentBase):
    """Fake agent that provides predictable responses for testing."""

    model_config = {"frozen": False}  # Allow mutation for testing
    step_count: int = 0
    user_messages: list[str] = []
    requested_write: bool = False
    requested_delete: bool = False

    def init_state(
        self, state: "ConversationState", on_event: "ConversationCallbackType"
    ) -> None:
        pass

    def step(
        self, state: "ConversationState", on_event: "ConversationCallbackType"
    ) -> None:
        """Provide predictable responses based on message."""

        last_event_str = str(state.events[-1])
        if "MessageEvent (user)" in last_event_str:
            self.user_messages.append(last_event_str)
            if "write 3 facts" in last_event_str:
                self.requested_write = True
                state.agent_status = AgentExecutionStatus.FINISHED
            elif "delete that file" in last_event_str:
                state.agent_status = AgentExecutionStatus.FINISHED
                self.requested_delete = True
        if self.step_count >= 5:
            # Should be error
            state.agent_status = AgentExecutionStatus.FINISHED
        self.step_count += 1


def test_hello_world_example():
    """Should request file is written then deleted."""
    fake_llm = LLM(
        model="fake-model",
        api_key=SecretStr("fake-key"),
    )
    fake_agent = FakeAgent(llm=fake_llm, tools={})

    example(fake_agent)

    assert fake_agent.requested_write
    assert fake_agent.requested_delete
    assert fake_agent.step_count == 2
