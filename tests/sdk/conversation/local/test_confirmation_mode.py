"""
Unit tests for confirmation mode functionality.

Tests the core behavior: pause action execution for user confirmation.
"""

from collections.abc import Sequence
from unittest.mock import MagicMock, patch

import pytest
from litellm import ChatCompletionMessageToolCall
from litellm.types.utils import (
    Choices,
    Function,
    Message as LiteLLMMessage,
    ModelResponse,
)
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.event import ActionEvent, MessageEvent, ObservationEvent
from openhands.sdk.event.base import EventBase
from openhands.sdk.event.llm_convertible import UserRejectObservation
from openhands.sdk.event.utils import get_unmatched_actions
from openhands.sdk.llm import LLM, ImageContent, Message, MetricsSnapshot, TextContent
from openhands.sdk.llm.utils.metrics import TokenUsage
from openhands.sdk.security.confirmation_policy import AlwaysConfirm, NeverConfirm
from openhands.sdk.tool import ToolExecutor, ToolSpec, register_tool
from openhands.sdk.tool.schema import ActionBase, ObservationBase
from openhands.sdk.tool.tool import Tool


class MockConfirmationModeAction(ActionBase):
    """Mock action schema for testing."""

    command: str


class MockConfirmationModeObservation(ObservationBase):
    """Mock observation schema for testing."""

    result: str

    @property
    def agent_observation(self) -> Sequence[TextContent | ImageContent]:
        return [TextContent(text=self.result)]


class TestConfirmationMode:
    """Test suite for confirmation mode functionality."""

    def setup_method(self):
        """Set up test fixtures."""

        # Create a real LLM instance for Agent validation
        self.llm = LLM(model="gpt-4", api_key=SecretStr("test-key"))

        # Create a MagicMock to override the completion method
        self.mock_llm = MagicMock()

        # Create a proper MetricsSnapshot mock for the LLM
        mock_token_usage = TokenUsage(
            model="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            cache_read_tokens=0,
            cache_write_tokens=0,
            context_window=4096,
            per_turn_token=150,
            response_id="test-response-id",
        )
        mock_metrics_snapshot = MetricsSnapshot(
            model_name="test-model",
            accumulated_cost=0.00075,
            max_budget_per_task=None,
            accumulated_token_usage=mock_token_usage,
        )
        self.mock_llm.metrics.get_snapshot.return_value = mock_metrics_snapshot

        class TestExecutor(
            ToolExecutor[MockConfirmationModeAction, MockConfirmationModeObservation]
        ):
            def __call__(
                self, action: MockConfirmationModeAction
            ) -> MockConfirmationModeObservation:
                return MockConfirmationModeObservation(
                    result=f"Executed: {action.command}"
                )

        def _make_tool() -> Sequence[Tool]:
            return [
                Tool(
                    name="test_tool",
                    description="A test tool",
                    action_type=MockConfirmationModeAction,
                    observation_type=MockConfirmationModeObservation,
                    executor=TestExecutor(),
                )
            ]

        register_tool("test_tool", _make_tool)

        self.agent = Agent(
            llm=self.llm,
            tools=[ToolSpec(name="test_tool")],
        )
        self.conversation = Conversation(agent=self.agent)

    def _mock_message_only(self, text: str = "Hello, how can I help you?") -> MagicMock:
        """Configure LLM to return a plain assistant message (no tool calls)."""
        return MagicMock(
            return_value=ModelResponse(
                id="response_msg",
                choices=[
                    Choices(message=LiteLLMMessage(role="assistant", content=text))
                ],
                created=0,
                model="test-model",
                object="chat.completion",
            )
        )

    def _make_pending_action(self) -> None:
        """Enable confirmation mode and produce a single pending action."""
        self.conversation.set_confirmation_policy(AlwaysConfirm())
        mock_completion = self._mock_action_once()
        with patch(
            "openhands.sdk.llm.llm.litellm_completion",
            return_value=mock_completion.return_value,
        ):
            self.conversation.send_message(
                Message(role="user", content=[TextContent(text="execute a command")])
            )
            self.conversation.run()
        assert self.conversation.state.confirmation_policy == AlwaysConfirm()
        assert (
            self.conversation.state.agent_status
            == AgentExecutionStatus.WAITING_FOR_CONFIRMATION
        )

    def _mock_action_once(
        self, call_id: str = "call_1", command: str = "test_command"
    ) -> MagicMock:
        """Configure LLM to return one tool call (action)."""
        tool_call = self._create_test_action(call_id=call_id, command=command).tool_call
        return MagicMock(
            return_value=ModelResponse(
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
        )

    def _mock_finish_action(self, message: str = "Task completed") -> MagicMock:
        """Configure LLM to return a FinishAction tool call."""
        tool_call = ChatCompletionMessageToolCall(
            id="finish_call_1",
            type="function",
            function=Function(name="finish", arguments=f'{{"message": "{message}"}}'),
        )

        return MagicMock(
            return_value=ModelResponse(
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
        )

    def _mock_multiple_actions_with_finish(self) -> MagicMock:
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

        return MagicMock(
            return_value=ModelResponse(
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
        )

    def _create_test_action(self, call_id="call_1", command="test_command"):
        """Helper to create test action events."""
        action = MockConfirmationModeAction(command=command)

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

    def test_mock_observation(self):
        # First test a round trip in the context of ObservationBase
        obs = MockConfirmationModeObservation(result="executed")

        # Now test embeddding this into an ObservationEvent
        event = ObservationEvent(
            observation=obs,
            action_id="action_id",
            tool_name="hammer",
            tool_call_id="tool_call_id",
        )
        dumped_event = event.model_dump()
        assert dumped_event["observation"]["kind"] == "MockConfirmationModeObservation"
        assert dumped_event["observation"]["result"] == "executed"
        loaded_event = event.model_validate(dumped_event)
        loaded_obs = loaded_event.observation
        assert isinstance(loaded_obs, MockConfirmationModeObservation)
        assert loaded_obs.result == "executed"

    def test_confirmation_mode_basic_functionality(self):
        """Test basic confirmation mode operations."""
        # Test initial state
        assert self.conversation.state.confirmation_policy == NeverConfirm()
        assert self.conversation.state.agent_status == AgentExecutionStatus.IDLE
        assert get_unmatched_actions(self.conversation.state.events) == []

        # Enable confirmation mode
        self.conversation.set_confirmation_policy(AlwaysConfirm())
        assert self.conversation.state.confirmation_policy == AlwaysConfirm()

        # Disable confirmation mode
        self.conversation.set_confirmation_policy(NeverConfirm())
        assert self.conversation.state.confirmation_policy == NeverConfirm()

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
        events: list[EventBase] = [action_event]

        # Test: action without observation should be pending
        unmatched = get_unmatched_actions(events)
        assert len(unmatched) == 1
        assert unmatched[0].id == action_event.id

        # Add observation for the action
        obs = MockConfirmationModeObservation(result="test result")

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
        self.conversation.set_confirmation_policy(AlwaysConfirm())
        mock_completion = self._mock_message_only("Hello, how can I help you?")
        with patch(
            "openhands.sdk.llm.llm.litellm_completion",
            return_value=mock_completion.return_value,
        ):
            self.conversation.send_message(
                Message(role="user", content=[TextContent(text="some prompt")])
            )
            self.conversation.run()

        assert self.conversation.state.agent_status == AgentExecutionStatus.FINISHED

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
            mock_completion = self._mock_message_only("Task completed successfully!")
            with patch(
                "openhands.sdk.llm.llm.litellm_completion",
                return_value=mock_completion.return_value,
            ):
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
            assert self.conversation.state.agent_status == AgentExecutionStatus.FINISHED
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
        self.conversation.set_confirmation_policy(AlwaysConfirm())

        # Mock LLM to return a single FinishAction
        mock_completion = self._mock_finish_action("Task completed successfully!")

        # Send a message that should trigger the finish action
        with patch(
            "openhands.sdk.llm.llm.litellm_completion",
            return_value=mock_completion.return_value,
        ):
            self.conversation.send_message(
                Message(
                    role="user", content=[TextContent(text="Please finish the task")]
                )
            )

            # Run the conversation
            self.conversation.run()

        # Single FinishAction should skip confirmation entirely
        assert (
            self.conversation.state.confirmation_policy == AlwaysConfirm()
        )  # Still in confirmation mode
        assert (
            self.conversation.state.agent_status == AgentExecutionStatus.FINISHED
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
        self.conversation.set_confirmation_policy(AlwaysConfirm())

        # Mock LLM to return both a regular action and a FinishAction
        mock_completion = self._mock_multiple_actions_with_finish()

        # Send a message that should trigger both actions
        with patch(
            "openhands.sdk.llm.llm.litellm_completion",
            return_value=mock_completion.return_value,
        ):
            self.conversation.send_message(
                Message(
                    role="user",
                    content=[TextContent(text="Execute command then finish")],
                )
            )

            # Run the conversation
            self.conversation.run()

        # Multiple actions should all wait for confirmation (including FinishAction)
        assert self.conversation.state.confirmation_policy == AlwaysConfirm()
        assert (
            self.conversation.state.agent_status
            == AgentExecutionStatus.WAITING_FOR_CONFIRMATION
        )

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

    def test_pause_during_confirmation_preserves_waiting_status(self):
        """Test that pausing during WAITING_FOR_CONFIRMATION preserves the status.

        This test reproduces the race condition issue where agent can be waiting
        for confirmation and the status is changed to paused instead. Waiting for
        confirmation is simply a special type of pause and should not be overridden.
        """
        # Create a pending action that puts agent in WAITING_FOR_CONFIRMATION state
        self._make_pending_action()

        # Verify we're in the expected state
        assert (
            self.conversation.state.agent_status
            == AgentExecutionStatus.WAITING_FOR_CONFIRMATION
        )
        assert self.conversation.state.confirmation_policy == AlwaysConfirm()

        # Call pause() while in WAITING_FOR_CONFIRMATION state
        self.conversation.pause()

        # Status should remain WAITING_FOR_CONFIRMATION, not change to PAUSED
        # This is the key fix: waiting for confirmation is a special type of pause
        assert (
            self.conversation.state.agent_status
            == AgentExecutionStatus.WAITING_FOR_CONFIRMATION
        )

        # Test that pause works correctly for other states
        # Reset to IDLE state
        with self.conversation._state:
            self.conversation._state.agent_status = AgentExecutionStatus.IDLE

        # Pause from IDLE should change status to PAUSED
        self.conversation.pause()
        assert self.conversation._state.agent_status == AgentExecutionStatus.PAUSED

        # Reset to RUNNING state
        with self.conversation._state:
            self.conversation._state.agent_status = AgentExecutionStatus.RUNNING

        # Pause from RUNNING should change status to PAUSED
        self.conversation.pause()
        assert self.conversation._state.agent_status == AgentExecutionStatus.PAUSED
