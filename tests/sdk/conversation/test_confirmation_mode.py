"""
Unit tests for confirmation mode functionality.

Tests the core behavior: pause action execution for user confirmation.
"""

from typing import TYPE_CHECKING, Any
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


if TYPE_CHECKING:
    pass


class TestConfirmationMode:
    """Test suite for confirmation mode functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        from openhands.sdk.tool import Tool
        from openhands.sdk.tool.schema import ActionBase, ObservationBase

        self.mock_llm = MagicMock()

        # Create a test tool for the agent
        TestAction = ActionBase.from_mcp_schema(
            "TestAction",
            {"type": "object", "properties": {"command": {"type": "string"}}},
        )

        class TestObservation(ObservationBase):
            result: str

            @property
            def agent_observation(self) -> str:
                return self.result

        from openhands.sdk.tool import ToolExecutor

        class TestExecutor(ToolExecutor[Any, Any]):  # type: ignore[type-arg]
            def __call__(self, action: Any) -> Any:
                return TestObservation(result=f"Executed: {action.command}")  # type: ignore[call-arg]

        test_tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema=TestAction,
            output_schema=TestObservation,
            executor=TestExecutor(),
        )

        self.agent = Agent(llm=self.mock_llm, tools=[test_tool])
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

    def test_getting_unmatched_events(self):
        """Test getting unmatched events (actions without observations)."""
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
        from litellm.types.utils import Choices, ModelResponse

        from openhands.sdk.event import MessageEvent
        from openhands.sdk.llm import Message, TextContent

        # Enable confirmation mode
        self.conversation.set_confirmation_mode(True)
        assert self.conversation.state.confirmation_mode is True

        # Test 1: Agent sends a message (no tool calls)
        # Mock LLM to return a message-only response
        from litellm.types.utils import Message as LiteLLMMessage

        message_response = ModelResponse(
            id="response_1",
            choices=[
                Choices(
                    message=LiteLLMMessage(
                        role="assistant", content="Hello, how can I help you?"
                    )
                )
            ],
            created=0,
            model="test-model",
            object="chat.completion",
        )
        self.mock_llm.completion.return_value = message_response

        # Send a message and run the conversation
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="some prompt")])
        )
        self.conversation.run()

        # Verify: message response doesn't ask for confirmation
        assert self.conversation.state.waiting_for_confirmation is False
        assert self.conversation.state.agent_finished is True

        # Verify a MessageEvent was generated
        message_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, MessageEvent) and event.source == "agent"
        ]
        assert len(message_events) == 1
        content = message_events[0].llm_message.content[0]
        assert isinstance(content, TextContent)
        assert content.text == "Hello, how can I help you?"

        # Test 2: Agent creates an action (with tool calls)
        # Reset agent state for next test
        self.conversation.state.agent_finished = False

        # Mock LLM to return an action response
        action_response = ModelResponse(
            id="response_2",
            choices=[
                Choices(
                    message=LiteLLMMessage(
                        role="assistant",
                        content="I'll execute a test command",
                        tool_calls=[self._create_test_action().tool_call],
                    )
                )
            ],
            created=0,
            model="test-model",
            object="chat.completion",
        )
        self.mock_llm.completion.return_value = action_response

        # Send another message and run
        self.conversation.send_message(
            Message(role="user", content=[TextContent(text="execute a command")])
        )
        self.conversation.run()

        # Verify: action response asks for confirmation
        assert self.conversation.state.agent_finished is False
        assert self.conversation.state.waiting_for_confirmation is True

        # Verify no observation has been generated yet (action not executed)
        observation_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, ObservationEvent)
        ]
        assert len(observation_events) == 0

        # Test 3: Call run() again to execute the pending action
        # Mock LLM to return a finish response (no more actions)
        finish_response = ModelResponse(
            id="response_3",
            choices=[
                Choices(
                    message=LiteLLMMessage(
                        role="assistant", content="Task completed successfully!"
                    )
                )
            ],
            created=0,
            model="test-model",
            object="chat.completion",
        )
        self.mock_llm.completion.return_value = finish_response

        # Run again - this should execute the pending action
        self.conversation.run()

        # Verify: observation was generated from running the action
        observation_events = [
            event
            for event in self.conversation.state.events
            if isinstance(event, ObservationEvent)
        ]
        assert len(observation_events) == 1
        assert observation_events[0].observation.result == "Executed: test_command"  # type: ignore[attr-defined]
        assert self.conversation.state.waiting_for_confirmation is False

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
