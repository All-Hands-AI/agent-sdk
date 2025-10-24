"""Tests for DelegateExecutor."""

import uuid
from unittest.mock import MagicMock

from openhands.tools.delegate import DelegateAction, DelegateExecutor


def create_mock_conversation():
    """Helper to create a mock conversation."""
    mock_conv = MagicMock()
    mock_conv.id = str(uuid.uuid4())
    return mock_conv


def test_delegation_manager_init():
    """Test DelegateExecutor initialization."""
    mock_conv = create_mock_conversation()
    manager = DelegateExecutor()

    # Test that the manager initializes properly
    assert not manager.is_task_in_progress()

    # Set parent conversation manually (normally done on first call)
    manager._parent_conversation = mock_conv

    # Test that parent conversation is set
    assert manager.parent_conversation == mock_conv
    assert str(manager.parent_conversation.id) == str(mock_conv.id)

    # Clean up
    manager.shutdown()


def test_send_to_sub_agent_not_found():
    """Test sending message to non-existent sub-agent."""
    mock_conv = create_mock_conversation()
    manager = DelegateExecutor(mock_conv)

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
    mock_conv = create_mock_conversation()
    manager = DelegateExecutor(mock_conv)

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
        conversation=mock_conversation,
        thread=mock_thread,
        state=SubAgentState.RUNNING,
        stop_event=mock_stop_event,
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
    # Create parent
    parent_id = str(uuid.uuid4())
    mock_parent_conv = MagicMock()
    mock_parent_conv.id = parent_id
    manager = DelegateExecutor()

    # Set parent conversation manually (normally done on first call)
    manager._parent_conversation = mock_parent_conv

    # Create child sub-agent
    child_id = str(uuid.uuid4())
    mock_child_conversation = MagicMock()
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = False
    mock_stop_event = MagicMock()

    import time

    from openhands.tools.delegate.impl import SubAgentInfo, SubAgentState

    sub_agent_info = SubAgentInfo(
        conversation_id=child_id,
        conversation=mock_child_conversation,
        thread=mock_thread,
        state=SubAgentState.RUNNING,
        stop_event=mock_stop_event,
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
    assert manager.parent_conversation == mock_parent_conv
    assert str(manager.parent_conversation.id) == parent_id

    # Clean up
    manager.shutdown()


def test_close_sub_agent_not_found():
    """Test closing non-existent sub-agent."""
    mock_conv = create_mock_conversation()
    manager = DelegateExecutor(mock_conv)

    # Close non-existent sub-agent
    action = DelegateAction(operation="close", sub_conversation_id="non-existent")
    result = manager._close_sub_agent(action)

    # Verify - missing sub-agents are treated as already cleaned up (success=True)
    assert result.success is True
    assert "already cleaned up" in result.message

    # Clean up
    manager.shutdown()
