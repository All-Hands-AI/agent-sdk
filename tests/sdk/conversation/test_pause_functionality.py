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
import time
from unittest.mock import MagicMock

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
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.tool import ActionBase, ObservationBase, Tool, ToolExecutor


class MockAction(ActionBase):
    """Mock action schema for testing."""

    command: str


class MockObservation(ObservationBase):
    """Mock observation schema for testing."""

    result: str

    @property  # pyright: ignore[reportIncompatibleMethodOverride]
    def agent_observation(self) -> str:
        return self.result


class SlowExecutor(ToolExecutor[MockAction, MockObservation]):
    """Executor that takes time to complete, allowing pause to be tested."""

    def __init__(self, delay: float = 0.1):
        self.delay = delay

    def __call__(self, action: MockAction) -> MockObservation:
        time.sleep(self.delay)
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

    def test_multiple_pause_calls_create_one_event(self):
        """Test requirement #1: Multiple pause method calls successively only create one PauseEvent."""  # noqa: E501
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

    def test_pause_while_running_in_separate_thread(self):
        """Test requirement #2: Calling conversation.pause() while conversation.run() is running in separate thread will pause the agent."""  # noqa: E501
        # Mock LLM to continuously return actions (infinite loop)
        self._mock_repeating_action("continuous_action")

        # Send initial message
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Start continuous work")])
        )

        # Start run() in a separate thread
        run_finished = threading.Event()
        run_exception: list[Exception | None] = [None]

        def run_agent():
            try:
                self.conversation.run()
            except Exception as e:
                run_exception[0] = e
            finally:
                run_finished.set()

        agent_thread = threading.Thread(target=run_agent, daemon=True)
        agent_thread.start()

        # Give the agent time to start running
        time.sleep(0.1)

        # Pause from main thread while agent is running
        self.conversation.pause()

        # Wait for run() to finish (should exit due to pause)
        assert run_finished.wait(timeout=2.0), "Agent did not stop after pause"
        agent_thread.join(timeout=0.1)

        # Verify no exception occurred
        assert run_exception[0] is None, f"Agent thread failed: {run_exception[0]}"

        # Verify agent is paused and not finished
        assert self.conversation.state.agent_paused is True
        assert self.conversation.state.agent_finished is False

        # Should have exactly one pause event
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 1

    def test_resume_paused_agent(self):
        """Test requirement #3: Calling conversation.run() on an already paused agent will resume it."""  # noqa: E501
        # Mock LLM to return a finishing message
        self._mock_message_only("Task completed successfully")

        # Send initial message
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Complete this task")])
        )

        # Pause the agent before running
        self.conversation.pause()
        assert self.conversation.state.agent_paused is True

        # Call run() on the paused agent - this should resume execution
        self.conversation.run()

        # After run(), the agent should have completed the task
        assert self.conversation.state.agent_finished is True
        assert self.conversation.state.agent_paused is False  # Reset during run()

        # Should have both pause event and agent response
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        agent_messages = [
            event
            for event in self.conversation.state.events
            if isinstance(event, MessageEvent) and event.source == "agent"
        ]

        assert len(pause_events) == 1  # From the pause() call
        assert len(agent_messages) == 1  # Agent completed the task

    def test_pause_resume_cycle_with_actions(self):
        """Test pause/resume cycle with actual agent actions."""
        # Mock LLM to return an action, then a finish message
        responses = [
            # First call: return an action
            ModelResponse(
                id="response_action",
                choices=[
                    Choices(
                        message=LiteLLMMessage(
                            role="assistant",
                            content="I'll execute the command",
                            tool_calls=[
                                ChatCompletionMessageToolCall(
                                    id="call_1",
                                    type="function",
                                    function=Function(
                                        name="test_tool",
                                        arguments='{"command": "test_action"}',
                                    ),
                                )
                            ],
                        )
                    )
                ],
                created=0,
                model="test-model",
                object="chat.completion",
            ),
            # Second call: return finish message
            ModelResponse(
                id="response_finish",
                choices=[
                    Choices(
                        message=LiteLLMMessage(
                            role="assistant", content="Task completed"
                        )
                    )
                ],
                created=0,
                model="test-model",
                object="chat.completion",
            ),
        ]
        self.mock_llm.completion.side_effect = responses

        # Send message and pause immediately
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Execute test command")])
        )
        self.conversation.pause()

        # Resume by calling run() - should execute action and finish
        self.conversation.run()

        # Verify completion
        assert self.conversation.state.agent_finished is True
        assert self.conversation.state.agent_paused is False

        # Should have pause event and action execution
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 1

    def _mock_repeating_action(self, command: str = "loop_forever") -> None:
        """Mock LLM to continuously return actions (for infinite loop testing)."""
        tool_call = ChatCompletionMessageToolCall(
            id="call_loop",
            type="function",
            function=Function(
                name="test_tool", arguments=f'{{"command": "{command}"}}'
            ),
        )

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
