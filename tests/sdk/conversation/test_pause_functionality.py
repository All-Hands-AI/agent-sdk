"""
Unit tests for pause functionality.

Tests the core behavior: pause agent execution between steps.
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
from openhands.sdk.tool import Tool, ToolExecutor
from openhands.sdk.tool.schema import ActionBase, ObservationBase


class MockAction(ActionBase):
    """Mock action schema for testing."""

    command: str


class MockObservation(ObservationBase):
    """Mock observation schema for testing."""

    result: str

    @property
    def agent_observation(self) -> str:
        return self.result


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

    def _mock_action_once(
        self, call_id: str = "call_1", command: str = "test_command"
    ) -> None:
        """Configure LLM to return one tool call (action)."""
        tool_call = ChatCompletionMessageToolCall(
            id=call_id,
            type="function",
            function=Function(
                name="test_tool", arguments=f'{{"command": "{command}"}}'
            ),
        )
        self.mock_llm.completion.return_value = ModelResponse(
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

        # Check that PauseEvent was added
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 1
        assert pause_events[0].source == "user"

    def test_pause_during_normal_execution(self):
        """Test pausing during normal agent execution."""
        # Mock LLM to return a message that finishes execution
        self._mock_message_only("Task completed")

        # Send message and start execution
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Hello")])
        )

        # Pause immediately (before run starts)
        self.conversation.pause()

        # Run should exit immediately due to pause
        self.conversation.run()

        # Agent should not be finished (paused before execution)
        assert self.conversation.state.agent_finished is False
        assert self.conversation.state.agent_paused is False  # Reset after pause

        # Should have pause event
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 1

    def test_pause_then_resume(self):
        """Test pausing and then resuming execution."""
        # Mock LLM to return a message that finishes execution
        self._mock_message_only("Task completed")

        # Send message
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Hello")])
        )

        # Pause and run (should exit immediately)
        self.conversation.pause()
        self.conversation.run()

        # Agent should not be finished
        assert self.conversation.state.agent_finished is False

        # Resume by calling run again
        self.conversation.run()

        # Now agent should be finished
        assert self.conversation.state.agent_finished is True

        # Should have agent message
        agent_messages = [
            event
            for event in self.conversation.state.events
            if isinstance(event, MessageEvent) and event.source == "agent"
        ]
        assert len(agent_messages) == 1

    def test_pause_with_threading(self):
        """Test pause functionality with threading (simulating CLI usage)."""

        # Mock LLM to simulate a slow operation
        def slow_completion(*args, **kwargs):
            time.sleep(0.1)  # Simulate slow LLM call
            return ModelResponse(
                id="response_msg",
                choices=[
                    Choices(message=LiteLLMMessage(role="assistant", content="Done"))
                ],
                created=0,
                model="test-model",
                object="chat.completion",
            )

        self.mock_llm.completion.side_effect = slow_completion

        # Send message
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Hello")])
        )

        # Start run in a separate thread
        run_finished = threading.Event()
        agent_finished = [False]

        def run_agent():
            self.conversation.run()
            agent_finished[0] = self.conversation.state.agent_finished
            run_finished.set()

        run_thread = threading.Thread(target=run_agent)
        run_thread.start()

        # Pause from main thread after a short delay
        time.sleep(0.05)  # Let the run start
        self.conversation.pause()

        # Wait for run to finish
        run_finished.wait(timeout=1.0)
        run_thread.join()

        # Agent should be finished (pause happened after LLM call completed)
        # Note: This tests the limitation that we can't interrupt mid-LLM call
        assert agent_finished[0] is True

        # Should have pause event
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 1

    def test_pause_with_confirmation_mode(self):
        """Test that pause works alongside confirmation mode."""
        # Enable confirmation mode
        self.conversation.set_confirmation_mode(True)

        # Mock action
        self._mock_action_once()

        # Send message
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Execute command")])
        )

        # Pause before running
        self.conversation.pause()

        # Run should exit due to pause (not confirmation)
        self.conversation.run()

        # Should be paused, not waiting for confirmation
        assert self.conversation.state.agent_paused is False  # Reset
        assert self.conversation.state.agent_waiting_for_confirmation is False
        assert self.conversation.state.agent_finished is False

        # Should have pause event
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 1

    def test_multiple_pause_calls(self):
        """Test multiple pause calls (should be idempotent)."""
        # Call pause multiple times
        self.conversation.pause()
        self.conversation.pause()
        self.conversation.pause()

        # Should have multiple pause events (each call creates an event)
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 3

        # But state should still be paused
        assert self.conversation.state.agent_paused is True

    def test_pause_event_properties(self):
        """Test PauseEvent properties and string representation."""
        self.conversation.pause()

        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 1

        pause_event = pause_events[0]
        assert pause_event.source == "user"
        assert "Agent execution paused" in str(pause_event)
        assert "PauseEvent" in str(pause_event)

    def test_pause_thread_safety(self):
        """Test that pause is thread-safe."""

        # Test concurrent pause calls from multiple threads
        def pause_worker():
            self.conversation.pause()

        threads = []
        for _ in range(10):
            thread = threading.Thread(target=pause_worker)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should have 10 pause events
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 10

        # State should be paused
        assert self.conversation.state.agent_paused is True
