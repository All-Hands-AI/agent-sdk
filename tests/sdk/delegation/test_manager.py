"""Tests for DelegationManager."""

from openhands.sdk.delegation.manager import DelegationManager


def test_delegation_manager_init():
    """Test DelegationManager initialization."""
    manager = DelegationManager()

    assert manager.conversations == {}
    assert manager.parent_to_children == {}
    assert manager.child_to_parent == {}


def test_spawn_sub_agent():
    """Test spawning a sub-agent using the simple implementation."""
    manager = DelegationManager()

    # Test create_simple_sub_agent which is the actual working method
    result = manager.create_simple_sub_agent("Test task")

    # Verify result
    assert isinstance(result, str)  # Should return a UUID string
    assert result in manager.conversations

    # Verify the sub-agent data structure
    sub_agent = manager.conversations[result]
    assert isinstance(sub_agent, dict)
    assert sub_agent["task"] == "Test task"
    assert sub_agent["status"] == "created"
    assert sub_agent["messages"] == []


def test_send_to_sub_agent_success():
    """Test sending message to sub-agent successfully."""
    manager = DelegationManager()

    # Create a simple sub-agent first
    sub_id = manager.create_simple_sub_agent("Test task")

    # Send message
    result = manager.send_to_sub_agent(sub_id, "Test message")

    # Verify
    assert result is True

    # Check that message was stored
    sub_agent = manager.conversations[sub_id]
    assert isinstance(sub_agent, dict)
    assert "Test message" in sub_agent["messages"]


def test_send_to_sub_agent_not_found():
    """Test sending message to non-existent sub-agent."""
    manager = DelegationManager()

    # Send message to non-existent sub-agent
    result = manager.send_to_sub_agent("non-existent", "Test message")

    # Verify
    assert result is False


def test_close_sub_agent_success():
    """Test closing sub-agent successfully."""
    manager = DelegationManager()

    # Create a simple sub-agent first
    sub_id = manager.create_simple_sub_agent("Test task")

    # Verify it exists
    assert sub_id in manager.conversations

    # Close sub-agent
    result = manager.close_sub_agent(sub_id)

    # Verify cleanup
    assert result is True
    assert sub_id not in manager.conversations


def test_close_sub_agent_not_found():
    """Test closing non-existent sub-agent."""
    manager = DelegationManager()

    # Close non-existent sub-agent
    result = manager.close_sub_agent("non-existent")

    # Verify
    assert result is False


def test_multiple_sub_agents():
    """Test managing multiple sub-agents."""
    manager = DelegationManager()

    # Create multiple simple sub-agents
    result1 = manager.create_simple_sub_agent("Task 1")
    result2 = manager.create_simple_sub_agent("Task 2")

    # Verify both sub-agents are tracked
    assert isinstance(result1, str)
    assert isinstance(result2, str)
    assert result1 != result2  # Should have different IDs
    assert len(manager.conversations) == 2
    assert result1 in manager.conversations
    assert result2 in manager.conversations

    # Verify task assignments
    sub_agent1 = manager.conversations[result1]
    sub_agent2 = manager.conversations[result2]
    assert isinstance(sub_agent1, dict)
    assert isinstance(sub_agent2, dict)
    assert sub_agent1["task"] == "Task 1"
    assert sub_agent2["task"] == "Task 2"


def test_simple_message_handling():
    """Test simple message handling for sub-agents."""
    manager = DelegationManager()

    # Create a simple sub-agent
    sub_id = manager.create_simple_sub_agent("Test task")

    # Send multiple messages
    assert manager.send_simple_message(sub_id, "Message 1") is True
    assert manager.send_simple_message(sub_id, "Message 2") is True

    # Verify messages are stored
    sub_agent = manager.conversations[sub_id]
    assert isinstance(sub_agent, dict)
    assert len(sub_agent["messages"]) == 2
    assert "Message 1" in sub_agent["messages"]
    assert "Message 2" in sub_agent["messages"]

    # Test sending to non-existent sub-agent
    assert manager.send_simple_message("non-existent", "Message") is False
