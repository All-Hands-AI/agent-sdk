"""Tests for DelegateExecutor."""

import uuid
from unittest.mock import MagicMock

from openhands.tools.delegate import DelegateAction, DelegateExecutor


def test_delegation_manager_init():
    """Test DelegateExecutor initialization."""
    manager = DelegateExecutor()

    assert manager.conversations == {}
    assert manager.child_to_parent == {}


def test_register_and_get_conversation():
    """Test registering and retrieving conversations."""
    manager = DelegateExecutor()

    # Create a mock conversation object with an ID
    mock_conv = MagicMock()
    mock_conv.id = str(uuid.uuid4())

    # Register the conversation
    manager.register_conversation(mock_conv)  # type: ignore

    # Verify it's registered
    assert str(mock_conv.id) in manager.conversations
    assert manager.get_conversation(str(mock_conv.id)) == mock_conv


def test_get_conversation_not_found():
    """Test getting a non-existent conversation."""
    manager = DelegateExecutor()

    # Try to get non-existent conversation
    result = manager.get_conversation("non-existent")

    # Verify
    assert result is None


def test_send_to_sub_agent_not_found():
    """Test sending message to non-existent sub-agent."""
    manager = DelegateExecutor()

    # Send message to non-existent sub-agent
    action = DelegateAction(
        operation="send", sub_conversation_id="non-existent", message="Test message"
    )
    result = manager._send_to_sub_agent(action)

    # Verify
    assert result.success is False


def test_close_sub_agent_success():
    """Test closing sub-agent successfully."""
    manager = DelegateExecutor()

    # Create a dict-based entry to close
    test_id = str(uuid.uuid4())
    manager.conversations[test_id] = {"task": "test"}

    # Verify it exists
    assert test_id in manager.conversations

    # Close sub-agent
    action = DelegateAction(operation="close", sub_conversation_id=test_id)
    result = manager._close_sub_agent(action)

    # Verify cleanup
    assert result.success is True
    assert test_id not in manager.conversations


def test_close_sub_agent_with_parent_relationship():
    """Test closing sub-agent that has parent-child relationships."""
    manager = DelegateExecutor()

    # Create parent and child entries
    parent_id = str(uuid.uuid4())
    child_id = str(uuid.uuid4())

    manager.conversations[parent_id] = {"task": "parent"}
    manager.conversations[child_id] = {"task": "child"}

    # Set up parent-child relationship
    manager.child_to_parent[child_id] = parent_id

    # Close child
    action = DelegateAction(operation="close", sub_conversation_id=child_id)
    result = manager._close_sub_agent(action)

    # Verify cleanup
    assert result.success is True
    assert child_id not in manager.conversations
    assert child_id not in manager.child_to_parent
    # Parent should still exist
    assert parent_id in manager.conversations


def test_close_sub_agent_not_found():
    """Test closing non-existent sub-agent."""
    manager = DelegateExecutor()

    # Close non-existent sub-agent
    action = DelegateAction(operation="close", sub_conversation_id="non-existent")
    result = manager._close_sub_agent(action)

    # Verify
    assert result.success is False
