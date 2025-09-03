"""Simple tests for confirmation mode functionality."""

from openhands.core.event import UserRejectsObservation
from openhands.core.llm import TextContent


def test_user_rejects_observation_creation():
    """Test creating a UserRejectsObservation."""
    rejection = UserRejectsObservation(
        action_id="test_action_id",
        tool_name="test_tool",
        tool_call_id="test_call_id",
        rejection_reason="User said no",
    )

    assert rejection.action_id == "test_action_id"
    assert rejection.tool_name == "test_tool"
    assert rejection.tool_call_id == "test_call_id"
    assert rejection.rejection_reason == "User said no"


def test_user_rejects_observation_to_llm_message():
    """Test UserRejectsObservation conversion to LLM message."""
    rejection = UserRejectsObservation(
        action_id="test_action_id",
        tool_name="test_tool",
        tool_call_id="test_call_id",
        rejection_reason="User said no",
    )

    message = rejection.to_llm_message()
    assert message.role == "tool"
    assert message.name == "test_tool"
    assert message.tool_call_id == "test_call_id"
    assert len(message.content) == 1
    assert isinstance(message.content[0], TextContent)
    assert message.content[0].text == "Action rejected: User said no"


def test_user_rejects_observation_str_representation():
    """Test UserRejectsObservation string representation."""
    rejection = UserRejectsObservation(
        action_id="test_action_id",
        tool_name="test_tool",
        tool_call_id="test_call_id",
        rejection_reason="User said no",
    )

    str_repr = str(rejection)
    assert "UserRejectsObservation (user)" in str_repr
    assert "Tool: test_tool" in str_repr
    assert "Reason: User said no" in str_repr
