"""
Unit tests for confirmation mode functionality.

Tests the core behavior: pause action execution for user confirmation.
"""

from unittest.mock import MagicMock

from litellm import ChatCompletionMessageToolCall
from litellm.types.utils import (
    Function,
)

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.event import ActionEvent, ObservationEvent
from openhands.sdk.event.llm_convertible import UserRejectsObservation
from openhands.sdk.llm import TextContent
from openhands.sdk.tool.schema import ActionBase, ObservationBase


class TestConfirmationMode:
    """Test suite for confirmation mode functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_llm = MagicMock()
        self.agent = Agent(llm=self.mock_llm, tools=[])
        self.conversation = Conversation(agent=self.agent)

    def _create_test_action(self, call_id="call_1", command="test_command"):
        """Helper to create test action events."""
        TestAction = ActionBase.from_mcp_schema(
            "TestAction",
            {"type": "object", "properties": {"command": {"type": "string"}}},
        )
        action = TestAction(command=command)  # type: ignore[call-arg]

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
        assert self.conversation.state.waiting_for_confirmation is False
        assert self.conversation.get_pending_actions() == []

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
            if isinstance(event, UserRejectsObservation)
        ]
        assert len(rejection_events) == 0

    def test_action_interception_and_pending_management(self):
        """Test action interception and pending action management."""
        # Create test action
        action_event = self._create_test_action()
        events: list = [action_event]

        # Test: action without observation should be pending
        unmatched = self.agent._get_unmatched_actions(events)
        assert len(unmatched) == 1
        assert unmatched[0].id == action_event.id

        # Add observation for the action
        TestObservation = ObservationBase.from_mcp_schema(
            "TestObservation",
            {"type": "object", "properties": {"result": {"type": "string"}}},
        )
        obs = TestObservation(result="test result")  # type: ignore[call-arg]

        obs_event = ObservationEvent(
            source="environment",
            observation=obs,
            action_id=action_event.id,
            tool_name="test_tool",
            tool_call_id="call_1",
        )
        events.append(obs_event)

        # Test: action with observation should not be pending
        unmatched = self.agent._get_unmatched_actions(events)
        assert len(unmatched) == 0

        # Test rejection functionality
        action_event2 = self._create_test_action("call_2", "test_command_2")
        events.append(action_event2)

        # Add rejection for the second action
        rejection = UserRejectsObservation(
            action_id=action_event2.id,
            tool_name="test_tool",
            tool_call_id="call_2",
            rejection_reason="Test rejection",
        )
        events.append(rejection)

        # Test: rejected action should not be pending
        unmatched = self.agent._get_unmatched_actions(events)
        assert len(unmatched) == 0

        # Test UserRejectsObservation functionality
        llm_message = rejection.to_llm_message()
        assert llm_message.role == "tool"
        assert llm_message.name == "test_tool"
        assert llm_message.tool_call_id == "call_2"
        assert isinstance(llm_message.content[0], TextContent)
        assert "Action rejected: Test rejection" in llm_message.content[0].text

    def test_message_vs_action_behavior(self):
        """Test confirmation mode handles message-only vs action responses."""
        # Enable confirmation mode
        self.conversation.set_confirmation_mode(True)
        assert self.conversation.state.confirmation_mode is True

        # When no actions are created, no pending actions exist
        pending_actions = self.conversation.get_pending_actions()
        assert len(pending_actions) == 0

        # Agent should not finish prematurely when no actions created
        assert self.conversation.state.agent_finished is False

        # Rejecting when no actions exist should not cause errors
        self.conversation.reject_pending_actions("No actions to reject")
        rejection_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, UserRejectsObservation)
        ]
        assert len(rejection_events) == 0

    def test_confirmation_workflow_integration(self):
        """Test confirmation workflow state transitions."""

        # Step 1: Enable confirmation mode
        self.conversation.set_confirmation_mode(True)
        assert self.conversation.state.confirmation_mode is True

        # Step 2: Simulate agent creating an action (what would happen in real workflow)
        action_event = self._create_test_action("call_123", "echo hello")
        self.conversation.state.events.append(action_event)

        # Step 3: Verify pending action detection works
        pending_actions = self.conversation.get_pending_actions()
        assert len(pending_actions) == 1
        assert pending_actions[0].tool_name == "test_tool"
        assert pending_actions[0].id == action_event.id

        # Step 4: Test explicit rejection workflow
        self.conversation.state.waiting_for_confirmation = True
        self.conversation.reject_pending_actions("User rejected the action")

        # After rejection, should no longer be waiting
        assert self.conversation.state.waiting_for_confirmation is False

        # Should have rejection event in history
        rejection_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, UserRejectsObservation)
        ]
        assert len(rejection_events) == 1
        assert rejection_events[0].action_id == action_event.id
        assert "User rejected the action" in rejection_events[0].rejection_reason

        # Step 5: Test that rejected actions are no longer pending
        pending_after_rejection = self.conversation.get_pending_actions()
        assert len(pending_after_rejection) == 0

        # Step 6: Test confirmation mode can be disabled
        self.conversation.set_confirmation_mode(False)
        assert self.conversation.state.confirmation_mode is False
