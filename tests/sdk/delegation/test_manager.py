"""Tests for DelegationManager."""

import uuid
from unittest.mock import MagicMock

from openhands.sdk.delegation.manager import DelegationManager


def test_delegation_manager_init():
    """Test DelegationManager initialization."""
    manager = DelegationManager()

    assert manager.conversations == {}
    assert manager.child_to_parent == {}


def test_register_and_get_conversation():
    """Test registering and retrieving conversations."""
    manager = DelegationManager()

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
    manager = DelegationManager()

    # Try to get non-existent conversation
    result = manager.get_conversation("non-existent")

    # Verify
    assert result is None


def test_get_conversation_returns_none_for_dict():
    """Test get_conversation returns None for dict entries."""
    manager = DelegationManager()

    # Store a dict-based entry (like old simple sub-agents might have)
    test_id = str(uuid.uuid4())
    manager.conversations[test_id] = {"task": "test", "messages": []}

    # get_conversation should return None since it's not a real conversation object
    result = manager.get_conversation(test_id)
    assert result is None


def test_send_to_sub_agent_not_found():
    """Test sending message to non-existent sub-agent."""
    manager = DelegationManager()

    # Send message to non-existent sub-agent
    result = manager.send_to_sub_agent("non-existent", "Test message")

    # Verify
    assert result is False


def test_send_to_sub_agent_with_dict():
    """Test sending message to a dict-based sub-agent entry."""
    manager = DelegationManager()

    # Create a dict-based entry (for backward compatibility)
    test_id = str(uuid.uuid4())
    manager.conversations[test_id] = {"task": "test", "messages": []}

    # Send message
    result = manager.send_to_sub_agent(test_id, "Test message")

    # Verify
    assert result is True
    conv_entry = manager.conversations[test_id]
    assert isinstance(conv_entry, dict)
    assert "Test message" in conv_entry["messages"]


def test_close_sub_agent_success():
    """Test closing sub-agent successfully."""
    manager = DelegationManager()

    # Create a dict-based entry to close
    test_id = str(uuid.uuid4())
    manager.conversations[test_id] = {"task": "test"}

    # Verify it exists
    assert test_id in manager.conversations

    # Close sub-agent
    result = manager.close_sub_agent(test_id)

    # Verify cleanup
    assert result is True
    assert test_id not in manager.conversations


def test_close_sub_agent_with_parent_relationship():
    """Test closing sub-agent that has parent-child relationships."""
    manager = DelegationManager()

    # Create parent and child entries
    parent_id = str(uuid.uuid4())
    child_id = str(uuid.uuid4())

    manager.conversations[parent_id] = {"task": "parent"}
    manager.conversations[child_id] = {"task": "child"}

    # Set up parent-child relationship
    manager.child_to_parent[child_id] = parent_id

    # Close child
    result = manager.close_sub_agent(child_id)

    # Verify cleanup
    assert result is True
    assert child_id not in manager.conversations
    assert child_id not in manager.child_to_parent
    # Parent should still exist
    assert parent_id in manager.conversations


def test_close_sub_agent_not_found():
    """Test closing non-existent sub-agent."""
    manager = DelegationManager()

    # Close non-existent sub-agent
    result = manager.close_sub_agent("non-existent")

    # Verify
    assert result is False
