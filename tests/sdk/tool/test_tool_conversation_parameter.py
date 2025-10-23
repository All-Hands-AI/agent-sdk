"""Test Tool conversation parameter functionality."""

from unittest.mock import Mock

from pydantic import Field

from openhands.sdk.conversation.base import BaseConversation
from openhands.sdk.tool import Observation, ToolDefinition, ToolExecutor
from openhands.sdk.tool.schema import Action


class TestAction(Action):
    """Test action for conversation parameter tests."""

    message: str = Field(description="Test message")


class TestObservation(Observation):
    """Test observation for conversation parameter tests."""

    result: str
    conversation_id: str | None = None

    @property
    def to_llm_content(self):  # type: ignore[override]
        from openhands.sdk.llm import TextContent

        return [TextContent(text=self.result)]


class TestExecutor(ToolExecutor[TestAction, TestObservation]):
    """Test executor that uses the conversation parameter."""

    def __call__(
        self, action: TestAction, conversation: BaseConversation | None = None
    ) -> TestObservation:
        """Execute with conversation parameter."""
        conversation_id = str(conversation.id) if conversation else None
        return TestObservation(
            result=f"Processed: {action.message}", conversation_id=conversation_id
        )


def test_tool_call_with_conversation_parameter():
    """Test that tool can be called with conversation parameter."""
    # Create a mock conversation
    mock_conversation = Mock(spec=BaseConversation)
    mock_conversation.id = "test-conversation-123"

    # Create tool with executor that uses conversation
    tool = ToolDefinition(
        name="test_tool",
        description="Test tool with conversation parameter",
        action_type=TestAction,
        observation_type=TestObservation,
        executor=TestExecutor(),
    )

    # Test calling with conversation parameter
    action = TestAction(message="Hello World")
    result = tool(action, conversation=mock_conversation)

    assert isinstance(result, TestObservation)
    assert result.result == "Processed: Hello World"
    assert result.conversation_id == "test-conversation-123"


def test_tool_call_without_conversation_parameter():
    """Test that tool can be called without conversation parameter (backward compatibility)."""  # noqa: E501
    # Create tool with executor that uses conversation
    tool = ToolDefinition(
        name="test_tool",
        description="Test tool with conversation parameter",
        action_type=TestAction,
        observation_type=TestObservation,
        executor=TestExecutor(),
    )

    # Test calling without conversation parameter
    action = TestAction(message="Hello World")
    result = tool(action)

    assert isinstance(result, TestObservation)
    assert result.result == "Processed: Hello World"
    assert result.conversation_id is None


def test_tool_call_with_none_conversation():
    """Test that tool can be called with explicit None conversation."""
    # Create tool with executor that uses conversation
    tool = ToolDefinition(
        name="test_tool",
        description="Test tool with conversation parameter",
        action_type=TestAction,
        observation_type=TestObservation,
        executor=TestExecutor(),
    )

    # Test calling with explicit None conversation
    action = TestAction(message="Hello World")
    result = tool(action, conversation=None)

    assert isinstance(result, TestObservation)
    assert result.result == "Processed: Hello World"
    assert result.conversation_id is None


class LegacyExecutor(ToolExecutor[TestAction, TestObservation]):
    """Legacy executor that doesn't use the conversation parameter."""

    def __call__(
        self, action: TestAction, conversation: BaseConversation | None = None
    ) -> TestObservation:
        """Execute without using conversation parameter."""
        return TestObservation(result=f"Legacy: {action.message}")


def test_legacy_executor_compatibility():
    """Test that legacy executors still work with the new signature."""
    # Create tool with legacy executor
    tool = ToolDefinition(
        name="legacy_tool",
        description="Legacy tool",
        action_type=TestAction,
        observation_type=TestObservation,
        executor=LegacyExecutor(),
    )

    # Create a mock conversation
    mock_conversation = Mock(spec=BaseConversation)
    mock_conversation.id = "test-conversation-456"

    # Test calling with conversation parameter (should work but ignore it)
    action = TestAction(message="Legacy Test")
    result = tool(action, conversation=mock_conversation)

    assert isinstance(result, TestObservation)
    assert result.result == "Legacy: Legacy Test"
    assert result.conversation_id is None  # Legacy executor doesn't set this


def test_executable_tool_protocol_with_conversation():
    """Test that ExecutableTool protocol works with conversation parameter."""
    # Create tool and get as executable
    tool = ToolDefinition(
        name="executable_tool",
        description="Executable tool test",
        action_type=TestAction,
        observation_type=TestObservation,
        executor=TestExecutor(),
    )

    executable_tool = tool.as_executable()

    # Create a mock conversation
    mock_conversation = Mock(spec=BaseConversation)
    mock_conversation.id = "executable-test-789"

    # Test calling through ExecutableTool protocol
    action = TestAction(message="Executable Test")
    result = executable_tool(action, conversation=mock_conversation)

    assert isinstance(result, TestObservation)
    assert result.result == "Processed: Executable Test"
    assert result.conversation_id == "executable-test-789"
