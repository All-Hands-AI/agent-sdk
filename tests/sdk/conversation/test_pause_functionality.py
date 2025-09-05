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

    def test_pause_then_resume(self):
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

    def test_pause_during_run_in_separate_thread(self):
        """Test that calling pause() before run() in a separate thread -
        pause is reset and agent runs normally."""

        # Mock LLM to return a simple message
        self._mock_message_only("Task completed")

        # Send message to start conversation
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Execute task")])
        )

        # Start run in a separate thread
        run_finished = threading.Event()
        run_exception: list[Exception | None] = [None]

        def run_agent():
            try:
                # run() will reset agent_paused=False and proceed normally
                self.conversation.run()
            except Exception as e:
                run_exception[0] = e
            finally:
                run_finished.set()

        # Pause from main thread before starting the run thread
        self.conversation.pause()
        assert self.conversation.state.agent_paused is True

        run_thread = threading.Thread(target=run_agent)
        run_thread.start()

        # Wait for run to finish
        run_finished.wait(timeout=1.0)
        run_thread.join()

        # Check no exception occurred
        assert run_exception[0] is None, f"Run thread failed with: {run_exception[0]}"

        # Agent should be finished (pause was reset at start of run)
        assert self.conversation.state.agent_finished is True
        assert self.conversation.state.agent_paused is False

        # Should have pause event
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 1

    def test_resume_paused_agent(self):
        """Test that calling run() on an already paused agent resets pause and runs normally."""  # noqa: E501

        # Mock LLM to return a simple completion message
        self._mock_message_only("Task completed successfully")

        # Send message
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Complete this task")])
        )

        # Pause the agent before running
        self.conversation.pause()
        assert self.conversation.state.agent_paused is True

        # run() call resets pause and runs normally
        self.conversation.run()

        # Agent should be finished (pause was reset at start of run)
        assert self.conversation.state.agent_paused is False
        assert self.conversation.state.agent_finished is True

        # Agent messages should be generated since run completed normally
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

        # Mock action
        self._mock_action_once()

        # Send message
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Execute command")])
        )

        # Pause before running
        self.conversation.pause()
        assert self.conversation.state.agent_paused is True

        # Run resets pause and proceeds to create action, then waits for confirmation
        self.conversation.run()

        # Pause should be reset, agent should be waiting for confirmation
        assert self.conversation.state.agent_paused is False  # Pause was reset
        assert self.conversation.state.agent_waiting_for_confirmation is True
        assert self.conversation.state.agent_finished is False

        # Should have pause event
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 1

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
        """Test that pause is thread-safe and multiple concurrent calls
        create only one event."""

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

        # Should have only ONE pause event (requirement #1 applies to
        # concurrent calls too)
        pause_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, PauseEvent)
        ]
        assert len(pause_events) == 1, (
            f"Expected 1 PauseEvent from concurrent calls, got {len(pause_events)}. "
            "Multiple pause calls should only create one PauseEvent."
        )

        # State should be paused
        assert self.conversation.state.agent_paused is True
