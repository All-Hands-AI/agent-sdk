"""Tests for DelegateExecutor."""

import uuid
from unittest.mock import MagicMock

from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.tools.delegate import DelegateExecutor


def create_mock_conversation():
    """Helper to create a mock conversation."""
    mock_conv = MagicMock()
    mock_conv.id = str(uuid.uuid4())
    mock_conv.state.agent_status = AgentExecutionStatus.FINISHED
    return mock_conv


def test_delegation_manager_init():
    """Test DelegateExecutor initialization."""
    mock_conv = create_mock_conversation()
    manager = DelegateExecutor()

    # Set parent conversation manually (normally done on first call)
    manager._parent_conversation = mock_conv

    # Test that the manager initializes properly
    assert not manager.is_task_in_progress()

    # Test that parent conversation is set
    assert manager.parent_conversation == mock_conv
    assert str(manager.parent_conversation.id) == str(mock_conv.id)
