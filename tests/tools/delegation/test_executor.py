"""Tests for DelegateExecutor."""

import uuid
from unittest.mock import MagicMock

from openhands.tools.delegate import DelegateAction, DelegateExecutor


def test_delegation_manager_init():
    """Test DelegateExecutor initialization."""
    manager = DelegateExecutor()

    # Test that the manager initializes properly
    assert manager.get_conversation("non-existent") is None
    assert not manager.is_task_in_progress("non-existent")

    # Clean up
    manager.shutdown()


def test_register_and_get_conversation():
    """Test registering and retrieving conversations."""
    manager = DelegateExecutor()

    # Create a mock conversation object with an ID
    mock_conv = MagicMock()
    mock_conv.id = str(uuid.uuid4())

    # Register the conversation
    manager.register_conversation(mock_conv)  # type: ignore

    # Verify it's registered
    assert manager.get_conversation(str(mock_conv.id)) == mock_conv

    # Clean up
    manager.shutdown()


def test_get_conversation_not_found():
    """Test getting a non-existent conversation."""
    manager = DelegateExecutor()

    # Try to get non-existent conversation
    result = manager.get_conversation("non-existent")

    # Verify
    assert result is None

    # Clean up
    manager.shutdown()


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

    # Clean up
    manager.shutdown()


def test_close_sub_agent_success():
    """Test closing sub-agent successfully."""
    manager = DelegateExecutor()

    # Create a mock sub-agent entry directly in the internal structure
    test_id = str(uuid.uuid4())
    mock_conversation = MagicMock()
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = False
    mock_stop_event = MagicMock()

    import time

    from openhands.tools.delegate.impl import SubAgentInfo, SubAgentState

    sub_agent_info = SubAgentInfo(
        conversation_id=test_id,
        parent_id="parent_id",
        conversation=mock_conversation,
        thread=mock_thread,
        state=SubAgentState.RUNNING,
        stop_event=mock_stop_event,
        message_queue=MagicMock(),
        created_at=time.time(),
    )

    with manager._lock:
        manager._sub_agents[test_id] = sub_agent_info

    # Close sub-agent
    action = DelegateAction(operation="close", sub_conversation_id=test_id)
    result = manager._close_sub_agent(action)

    # Verify cleanup
    assert result.success is True

    # Clean up
    manager.shutdown()


def test_close_sub_agent_with_parent_relationship():
    """Test closing sub-agent that has parent-child relationships."""
    manager = DelegateExecutor()

    # Create parent and child entries
    parent_id = str(uuid.uuid4())
    child_id = str(uuid.uuid4())

    # Register parent conversation
    mock_parent_conv = MagicMock()
    mock_parent_conv.id = parent_id
    manager.register_conversation(mock_parent_conv)

    # Create child sub-agent
    mock_child_conversation = MagicMock()
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = False
    mock_stop_event = MagicMock()

    import time

    from openhands.tools.delegate.impl import SubAgentInfo, SubAgentState

    sub_agent_info = SubAgentInfo(
        conversation_id=child_id,
        parent_id=parent_id,
        conversation=mock_child_conversation,
        thread=mock_thread,
        state=SubAgentState.RUNNING,
        stop_event=mock_stop_event,
        message_queue=MagicMock(),
        created_at=time.time(),
    )

    with manager._lock:
        manager._sub_agents[child_id] = sub_agent_info

    # Close child
    action = DelegateAction(operation="close", sub_conversation_id=child_id)
    result = manager._close_sub_agent(action)

    # Verify cleanup
    assert result.success is True
    # Parent should still exist
    assert manager.get_conversation(parent_id) == mock_parent_conv

    # Clean up
    manager.shutdown()


def test_close_sub_agent_not_found():
    """Test closing non-existent sub-agent."""
    manager = DelegateExecutor()

    # Close non-existent sub-agent
    action = DelegateAction(operation="close", sub_conversation_id="non-existent")
    result = manager._close_sub_agent(action)

    # Verify
    assert result.success is False

    # Clean up
    manager.shutdown()
