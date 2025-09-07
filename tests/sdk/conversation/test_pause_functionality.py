"""
Unit tests for pause functionality.

Tests the core behavior: pause agent execution between steps.
Key requirements:
1. Multiple pause method calls successively only create one PauseEvent
2. Calling conversation.pause() while conversation.run() is still running in a
   separate thread will pause the agent
3. Calling conversation.run() on an already paused agent will resume it
"""

import threading
from unittest.mock import MagicMock

import pytest
from litellm import ChatCompletionMessageToolCall
from litellm.types.utils import (
    Choices,
    Function,
    Message as LiteLLMMessage,
    ModelResponse,
)

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.event import MessageEvent, PauseEvent
from openhands.sdk.llm import ImageContent, Message, TextContent
from openhands.sdk.tool import ActionBase, ObservationBase, Tool, ToolExecutor


class MockAction(ActionBase):
    """Mock action schema for testing."""

    command: str


class MockObservation(ObservationBase):
    """Mock observation schema for testing."""

    result: str

    @property
    def agent_observation(self) -> list[TextContent | ImageContent]:
        return [TextContent(text=self.result)]


class BlockingExecutor(ToolExecutor[MockAction, MockObservation]):
    def __init__(self, step_entered: threading.Event):
        self.step_entered = step_entered

    def __call__(self, action: MockAction) -> MockObservation:
        # Signal we've entered tool execution for this step
        self.step_entered.set()
        return MockObservation(result=f"Executed: {action.command}")


class TestPauseFunctionality:
    """Test suite for pause functionality."""

    def setup_method(self):
        """Set up test fixtures."""

        self.mock_llm = MagicMock()

        class TestExecutor(ToolExecutor[MockAction, MockObservation]):
            def __call__(self, action: MockAction) -> MockObservation:
                return MockObservation(result=f"Executed: {action.command}")

        test_tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=MockAction,
            output_schema=MockObservation,
            executor=TestExecutor(),
        )

        self.agent = Agent(llm=self.mock_llm, tools=[test_tool])
        self.conversation = Conversation(agent=self.agent)

    def _mock_message_only(self, text: str = "Hello, how can I help you?") -> None:
        """Configure LLM to return a plain assistant message (no tool calls)."""
        self.mock_llm.completion.return_value = ModelResponse(
            id="response_msg",
            choices=[Choices(message=LiteLLMMessage(role="assistant", content=text))],
            created=0,
            model="test-model",
            object="chat.completion",
        )

    def _mock_action(
        self, call_id: str = "call_1", command: str = "test_command", once=True
    ) -> None:
        """Configure LLM to return one tool call (action)."""
        tool_call = ChatCompletionMessageToolCall(
            id=call_id,
            type="function",
            function=Function(
                name="test_tool", arguments=f'{{"command": "{command}"}}'
            ),
        )
        response = ModelResponse(
            id="response_action",
            choices=[
                Choices(
                    message=LiteLLMMessage(
                        role="assistant",
                        content=f"I'll execute {command}",
                        tool_calls=[tool_call],
                    )
                )
            ],
            created=0,
            model="test-model",
            object="chat.completion",
        )
        if once:
            self.mock_llm.completion.return_value = response
        else:
            self.mock_llm.completion.side_effect = response

    def _mock_finish_action(self, message: str = "Task completed") -> None:
        """Configure LLM to return a FinishAction tool call."""
        tool_call = ChatCompletionMessageToolCall(
            id="finish_call_1",
            type="function",
            function=Function(name="finish", arguments=f'{{"message": "{message}"}}'),
        )

        self.mock_llm.completion.return_value = ModelResponse(
            id="response_finish",
            choices=[
                Choices(
                    message=LiteLLMMessage(
                        role="assistant",
                        content=f"I'll finish with: {message}",
                        tool_calls=[tool_call],
                    )
                )
            ],
            created=0,
            model="test-model",
            object="chat.completion",
        )

    def test_pause_basic_functionality(self):
        """Test basic pause operations."""
        # Test initial state
        assert self.conversation.state.agent_paused is False
        assert len(self.conversation.state.events) == 1  # System prompt event

        # Test pause method
        self.conversation.pause()
        assert self.conversation.state.agent_paused is True

        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 1
        assert pause_events[0].source == "user"

    def test_pause_during_normal_execution(self):
        """Test pausing before run() starts - pause is reset and agent runs normally."""
        # Mock LLM to return a message that finishes execution
        self._mock_message_only("Task completed")

        # Send message and start execution
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Hello")])
        )

        # Pause immediately (before run starts)
        self.conversation.pause()

        # Verify pause was set
        assert self.conversation.state.agent_paused is True

        # Run resets pause flag at start and proceeds normally
        self.conversation.run()

        # Agent should be finished (pause was reset at start of run)
        assert self.conversation.state.agent_finished is True
        # Pause flag is reset to False at start of run()
        assert self.conversation.state.agent_paused is False

        # Should have pause event from the pause() call
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 1

    def test_resume_paused_agent(self):
        """Test pausing before run() - pause is reset and agent runs normally."""
        # Mock LLM to return a message that finishes execution
        self._mock_message_only("Task completed")

        # Send message
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Hello")])
        )

        # Pause before run
        self.conversation.pause()
        assert self.conversation.state.agent_paused is True

        # First run() call resets pause and runs normally
        self.conversation.run()

        # Agent should be finished (pause was reset at start of run)
        assert self.conversation.state.agent_finished is True
        assert self.conversation.state.agent_paused is False

        # Should have agent message since run completed normally
        agent_messages = [
            event
            for event in self.conversation.state.events
            if isinstance(event, MessageEvent) and event.source == "agent"
        ]
        assert len(agent_messages) == 1  # Agent ran and completed

    def test_pause_with_confirmation_mode(self):
        """Test that pause before run() with confirmation mode - pause is reset and agent waits for confirmation."""  # noqa: E501
        # Enable confirmation mode
        self.conversation.set_confirmation_mode(True)
        self.conversation.pause()
        assert self.conversation.state.agent_paused is True

        # Mock action
        self._mock_action()

        # Send message
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Execute command")])
        )

        # Run resets pause and proceeds to create action, then waits for confirmation
        self.conversation.run()

        # Pause should be reset, agent should be waiting for confirmation
        assert self.conversation.state.agent_paused is False  # Pause was reset
        assert self.conversation.state.agent_waiting_for_confirmation is True
        assert self.conversation.state.agent_finished is False

        # Action did not execute
        agent_messages = [
            event
            for event in self.conversation.state.events
            if isinstance(event, ActionBase) and event.source == "agent"
        ]
        assert len(agent_messages) == 0

    def test_multiple_pause_calls_create_one_event(self):
        """Test that multiple successive pause calls only create one PauseEvent."""
        # Call pause multiple times successively
        self.conversation.pause()
        self.conversation.pause()
        self.conversation.pause()

        # Should have only ONE pause event (requirement #1)
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 1, (
            f"Expected 1 PauseEvent, got {len(pause_events)}. "
            "Multiple successive pause calls should only create one PauseEvent."
        )

        # State should be paused
        assert self.conversation.state.agent_paused is True

    def _mock_repeating_action(self, command: str = "loop_forever") -> None:
        tool_call = ChatCompletionMessageToolCall(
            id="call_loop",
            type="function",
            function=Function(
                name="test_tool", arguments=f'{{"command": "{command}"}}'
            ),
        )

        import time

        def side_effect(*_args, **_kwargs):
            return ModelResponse(
                id="response_action_loop",
                choices=[
                    Choices(
                        message=LiteLLMMessage(
                            role="assistant",
                            content=f"I'll execute {command}",
                            tool_calls=[tool_call],
                        )
                    )
                ],
                created=int(time.time()),
                model="test-model",
                object="chat.completion",
            )

        self.mock_llm.completion.side_effect = side_effect

    @pytest.mark.timeout(3)
    def test_pause_while_running_continuous_actions(self):
        step_entered = threading.Event()
        blocking_tool = Tool(
            name="test_tool",
            description="Blocking tool for pause test",
            input_schema=MockAction,
            output_schema=MockObservation,
            executor=BlockingExecutor(step_entered),
        )
        agent = Agent(llm=self.mock_llm, tools=[blocking_tool])
        conversation = Conversation(agent=agent)

        # Swap them in for this test only
        self.agent = agent
        self.conversation = conversation

        # LLM continuously emits actions (no finish)
        self._mock_repeating_action()

        # Seed a user message
        self.conversation.send_message(
            Message(
                role="user", content=[TextContent(text="Loop actions until paused")]
            )
        )

        run_exc: list[Exception | None] = [None]
        finished = threading.Event()

        def run_agent():
            try:
                self.conversation.run()
            except Exception as e:
                run_exc[0] = e
            finally:
                finished.set()

        t = threading.Thread(target=run_agent, daemon=True)
        t.start()

        # Wait until we're *inside* tool execution of the current iteration
        assert step_entered.wait(timeout=3.0), "Agent never reached tool execution"
        self.conversation.pause()
        assert self.conversation.state.agent_paused is True

        assert finished.wait(timeout=3.0), "run() did not exit after pause"
        t.join(timeout=0.1)
        assert run_exc[0] is None, f"Run thread failed with: {run_exc[0]}"

        # paused, not finished, exactly one PauseEvent
        assert self.conversation.state.agent_paused is True
        assert self.conversation.state.agent_finished is False
        pause_events = [
            e for e in self.conversation.state.events if isinstance(e, PauseEvent)
        ]
        assert len(pause_events) == 1, f"Expected 1 PauseEvent, got {len(pause_events)}"
