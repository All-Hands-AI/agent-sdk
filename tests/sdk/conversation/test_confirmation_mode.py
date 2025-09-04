"""
Unit tests for confirmation mode functionality.

Tests the core behavior: pause action execution for user confirmation.
"""

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
from openhands.sdk.event import ActionEvent, MessageEvent, ObservationEvent
from openhands.sdk.event.llm_convertible import UserRejectObservation
from openhands.sdk.event.utils import get_unmatched_actions
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


class TestConfirmationMode:
    """Test suite for confirmation mode functionality."""

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

    def _make_pending_action(self) -> None:
        """Enable confirmation mode and produce a single pending action."""
        self.conversation.set_confirmation_mode(True)
        self._mock_action_once()
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="execute a command")])
        )
        self.conversation.run()
        assert self.conversation.state.confirmation_mode is True
        assert self.conversation.state.agent_waiting_for_confirmation is True

    def _mock_action_once(
        self, call_id: str = "call_1", command: str = "test_command"
    ) -> None:
        """Configure LLM to return one tool call (action)."""
        tool_call = self._create_test_action(call_id=call_id, command=command).tool_call
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

    def _mock_multiple_actions_with_finish(self) -> None:
        """Configure LLM to return both a regular action and a FinishAction."""
        regular_tool_call = ChatCompletionMessageToolCall(
            id="call_1",
            type="function",
            function=Function(
                name="test_tool", arguments='{"command": "test_command"}'
            ),
        )

        finish_tool_call = ChatCompletionMessageToolCall(
            id="finish_call_1",
            type="function",
            function=Function(
                name="finish", arguments='{"message": "Task completed!"}'
            ),
        )

        self.mock_llm.completion.return_value = ModelResponse(
            id="response_multiple",
            choices=[
                Choices(
                    message=LiteLLMMessage(
                        role="assistant",
                        content="I'll execute the command and then finish",
                        tool_calls=[regular_tool_call, finish_tool_call],
                    )
                )
            ],
            created=0,
            model="test-model",
            object="chat.completion",
        )

    def _create_test_action(self, call_id="call_1", command="test_command"):
        """Helper to create test action events."""
        action = MockAction(command=command)

        tool_call = ChatCompletionMessageToolCall(
            id=call_id,
            type="function",
            function=Function(
                name="test_tool", arguments=f'{{"command": "{command}"}}'
            ),
        )

        return ActionEvent(
            source="agent",
            thought=[TextContent(text="Test thought")],
            action=action,
            tool_name="test_tool",
            tool_call_id=call_id,
            tool_call=tool_call,
            llm_response_id="response_1",
        )

    def test_confirmation_mode_basic_functionality(self):
        """Test basic confirmation mode operations."""
        # Test initial state
        assert self.conversation.state.confirmation_mode is False
        assert self.conversation.state.agent_waiting_for_confirmation is False
        assert get_unmatched_actions(self.conversation.state.events) == []

        # Enable confirmation mode
        self.conversation.set_confirmation_mode(True)
        assert self.conversation.state.confirmation_mode is True

        # Disable confirmation mode
        self.conversation.set_confirmation_mode(False)
        assert self.conversation.state.confirmation_mode is False

        # Test rejecting when no actions exist doesn't raise error
        self.conversation.reject_pending_actions("Nothing to reject")
        rejection_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, UserRejectObservation)
        ]
        assert len(rejection_events) == 0

    def test_getting_unmatched_events(self):
        """Test getting unmatched events (actions without observations)."""
        # Create test action
        action_event = self._create_test_action()
        events: list = [action_event]

        # Test: action without observation should be pending
        unmatched = get_unmatched_actions(events)
        assert len(unmatched) == 1
        assert unmatched[0].id == action_event.id

        # Add observation for the action
        obs = MockObservation(result="test result")

        obs_event = ObservationEvent(
            source="environment",
            observation=obs,
            action_id=action_event.id,
            tool_name="test_tool",
            tool_call_id="call_1",
        )
        events.append(obs_event)

        # Test: action with observation should not be pending
        unmatched = get_unmatched_actions(events)
        assert len(unmatched) == 0

        # Test rejection functionality
        action_event2 = self._create_test_action("call_2", "test_command_2")
        events.append(action_event2)

        # Add rejection for the second action
        rejection = UserRejectObservation(
            action_id=action_event2.id,
            tool_name="test_tool",
            tool_call_id="call_2",
            rejection_reason="Test rejection",
        )
        events.append(rejection)

        # Test: rejected action should not be pending
        unmatched = get_unmatched_actions(events)
        assert len(unmatched) == 0

        # Test UserRejectObservation functionality
        llm_message = rejection.to_llm_message()
        assert llm_message.role == "tool"
        assert llm_message.name == "test_tool"
        assert llm_message.tool_call_id == "call_2"
        assert isinstance(llm_message.content[0], TextContent)
        assert "Action rejected: Test rejection" in llm_message.content[0].text

    def test_message_only_in_confirmation_mode_does_not_wait(self):
        """Don't confirm agent messages."""
        self.conversation.set_confirmation_mode(True)
        self._mock_message_only("Hello, how can I help you?")
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="some prompt")])
        )
        self.conversation.run()

        assert self.conversation.state.agent_waiting_for_confirmation is False
        assert self.conversation.state.agent_finished is True

        msg_events = [
            e
            for e in self.conversation.state.events
            if isinstance(e, MessageEvent) and e.source == "agent"
        ]
        assert len(msg_events) == 1
        assert isinstance(msg_events[0].llm_message.content[0], TextContent)
        assert msg_events[0].llm_message.content[0].text == "Hello, how can I help you?"

    @pytest.mark.parametrize("should_reject", [True, False])
    def test_action_then_confirm_or_reject(self, should_reject: bool):
        """
        Start in confirmation mode, get a pending action, then:
        - if should_reject is False: confirm by calling conversation.run()
        - if should_reject is True: reject via conversation.reject_pending_action
        """
        # Create a single pending action
        self._make_pending_action()

        if not should_reject:
            # Confirm path per your instruction: call run() to execute pending action
            self._mock_message_only("Task completed successfully!")
            self.conversation.run()

            # Expect an observation (tool executed) and no rejection
            obs_events = [
                e
                for e in self.conversation.state.events
                if isinstance(e, ObservationEvent)
            ]
            assert len(obs_events) == 1
            assert obs_events[0].observation.result == "Executed: test_command"  # type: ignore[attr-defined]
            rejection_events = [
                e
                for e in self.conversation.state.events
                if isinstance(e, UserRejectObservation)
            ]
            assert len(rejection_events) == 0
            assert self.conversation.state.agent_waiting_for_confirmation is False
        else:
            self.conversation.reject_pending_actions("Not safe to run")

            # Expect a rejection event and no observation
            rejection_events = [
                e
                for e in self.conversation.state.events
                if isinstance(e, UserRejectObservation)
            ]
            assert len(rejection_events) == 1
            obs_events = [
                e
                for e in self.conversation.state.events
                if isinstance(e, ObservationEvent)
            ]
            assert len(obs_events) == 0

    def test_single_finish_action_skips_confirmation_entirely(self):
        """Test that a single FinishAction skips confirmation entirely."""
        # Enable confirmation mode
        self.conversation.set_confirmation_mode(True)

        # Mock LLM to return a single FinishAction
        self._mock_finish_action("Task completed successfully!")

        # Send a message that should trigger the finish action
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="Please finish the task")])
        )

        # Run the conversation
        self.conversation.run()

        # Single FinishAction should skip confirmation entirely
        assert (
            self.conversation.state.confirmation_mode is True
        )  # Still in confirmation mode
        assert (
            self.conversation.state.agent_waiting_for_confirmation is False
        )  # But not waiting
        assert (
            self.conversation.state.agent_finished is True
        )  # Agent should be finished

        # Should have no pending actions (FinishAction was executed immediately)
        pending_actions = get_unmatched_actions(self.conversation.state.events)
        assert len(pending_actions) == 0

        # Should have an observation event (action was executed)
        obs_events = [
            e for e in self.conversation.state.events if isinstance(e, ObservationEvent)
        ]
        assert len(obs_events) == 1
        assert obs_events[0].observation.message == "Task completed successfully!"  # type: ignore[attr-defined]

    def test_multiple_actions_with_finish_still_require_confirmation(self):
        """Test that multiple actions (including FinishAction) still require confirmation."""  # noqa: E501
        # Enable confirmation mode
        self.conversation.set_confirmation_mode(True)

        # Mock LLM to return both a regular action and a FinishAction
        self._mock_multiple_actions_with_finish()

        # Send a message that should trigger both actions
        self.conversation.send_message(
            Message(
                role="user", content=[TextContent(text="Execute command then finish")]
            )
        )

        # Run the conversation
        self.conversation.run()

        # Multiple actions should all wait for confirmation (including FinishAction)
        assert self.conversation.state.confirmation_mode is True
        assert self.conversation.state.agent_waiting_for_confirmation is True
        assert (
            self.conversation.state.agent_finished is False
        )  # No actions executed yet

        # Should have pending actions (both actions)
        pending_actions = get_unmatched_actions(self.conversation.state.events)
        assert len(pending_actions) == 2
        action_tools = [action.tool_name for action in pending_actions]
        assert "test_tool" in action_tools
        assert "finish" in action_tools

        # Should have no observation events (no actions executed yet)
        obs_events = [
            e for e in self.conversation.state.events if isinstance(e, ObservationEvent)
        ]
        assert len(obs_events) == 0
