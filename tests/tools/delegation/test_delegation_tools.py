"""Tests for delegation tools."""

from openhands.tools.delegation.definition import DelegateAction, DelegateObservation
from openhands.tools.delegation.impl import DelegateExecutor


def test_delegate_action_creation():
    """Test creating DelegateAction instances."""
    # Test spawn action
    spawn_action = DelegateAction(operation="spawn", task="Analyze code quality")
    assert spawn_action.operation == "spawn"
    assert spawn_action.task == "Analyze code quality"
    assert spawn_action.sub_conversation_id is None
    assert spawn_action.message is None

    # Test send action
    send_action = DelegateAction(
        operation="send", sub_conversation_id="sub-123", message="Hello"
    )
    assert send_action.operation == "send"
    assert send_action.sub_conversation_id == "sub-123"
    assert send_action.message == "Hello"
    assert send_action.task is None


def test_delegate_observation_creation():
    """Test creating DelegateObservation instances."""
    observation = DelegateObservation(
        sub_conversation_id="sub-123",
        status="created",
        message="Sub-agent created successfully",
        result="Task assigned",
    )
    assert observation.sub_conversation_id == "sub-123"
    assert observation.status == "created"
    assert observation.message == "Sub-agent created successfully"
    assert observation.result == "Task assigned"


def test_delegate_executor_spawn():
    """Test DelegateExecutor spawn operation."""
    # Create executor (it creates its own DelegationManager)
    executor = DelegateExecutor()

    # Create spawn action
    action = DelegateAction(operation="spawn", task="Analyze code quality")

    # Execute action
    observation = executor(action)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.sub_conversation_id is not None
    assert observation.status == "created"
    assert "Sub-agent created successfully" in observation.message
    assert (
        observation.result is not None
        and "Task assigned: Analyze code quality" in observation.result
    )


def test_delegate_executor_send():
    """Test DelegateExecutor send operation."""
    executor = DelegateExecutor()

    # First spawn a sub-agent
    spawn_action = DelegateAction(operation="spawn", task="Test task")
    spawn_result = executor(spawn_action)
    sub_id = spawn_result.sub_conversation_id

    # Send message to sub-agent
    send_action = DelegateAction(
        operation="send", sub_conversation_id=sub_id, message="Hello sub-agent"
    )
    observation = executor(send_action)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.sub_conversation_id == sub_id
    assert observation.status == "message_sent"
    assert f"Message sent to sub-agent {sub_id}" in observation.message
    assert (
        observation.result is not None
        and "Message: Hello sub-agent" in observation.result
    )


def test_delegate_executor_send_invalid_id():
    """Test DelegateExecutor send with invalid sub-agent ID."""
    executor = DelegateExecutor()

    # Send message to non-existent sub-agent
    action = DelegateAction(
        operation="send", sub_conversation_id="invalid-id", message="Hello"
    )
    observation = executor(action)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.status == "error"
    assert "Failed to send message" in observation.message


def test_delegate_executor_close():
    """Test DelegateExecutor close operation."""
    executor = DelegateExecutor()

    # First spawn a sub-agent
    spawn_action = DelegateAction(operation="spawn", task="Test task")
    spawn_result = executor(spawn_action)
    sub_id = spawn_result.sub_conversation_id

    # Close the sub-agent
    close_action = DelegateAction(operation="close", sub_conversation_id=sub_id)
    observation = executor(close_action)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.sub_conversation_id == sub_id
    assert observation.status == "closed"
    assert f"Sub-agent {sub_id} closed successfully" in observation.message


def test_delegate_executor_status():
    """Test DelegateExecutor status operation."""
    executor = DelegateExecutor()

    # First spawn a sub-agent
    spawn_action = DelegateAction(operation="spawn", task="Test task")
    spawn_result = executor(spawn_action)
    sub_id = spawn_result.sub_conversation_id

    # Get status of the sub-agent
    status_action = DelegateAction(operation="status", sub_conversation_id=sub_id)
    observation = executor(status_action)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.sub_conversation_id == sub_id
    assert observation.status == "active"
    assert f"Sub-agent {sub_id} is created" in observation.message
    assert (
        observation.result is not None
        and "Agent status: created, Task: Test task" in observation.result
    )


def test_delegate_executor_status_not_found():
    """Test DelegateExecutor status with non-existent sub-agent."""
    executor = DelegateExecutor()

    # Get status of non-existent sub-agent
    status_action = DelegateAction(operation="status", sub_conversation_id="invalid-id")
    observation = executor(status_action)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.status == "not_found"
    assert "Sub-agent invalid-id not found" in observation.message


def test_delegate_executor_spawn_missing_task():
    """Test DelegateExecutor spawn without task."""
    executor = DelegateExecutor()

    # Create spawn action without task
    action = DelegateAction(operation="spawn")

    # Execute action
    observation = executor(action)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.status == "error"
    assert "Task is required for spawn operation" in observation.message


def test_delegate_executor_send_missing_params():
    """Test DelegateExecutor send with missing parameters."""
    executor = DelegateExecutor()

    # Test missing sub_conversation_id
    action1 = DelegateAction(operation="send", message="Hello")
    observation1 = executor(action1)
    assert observation1.status == "error"
    assert "Sub-conversation ID is required" in observation1.message

    # Test missing message
    action2 = DelegateAction(operation="send", sub_conversation_id="sub-123")
    observation2 = executor(action2)
    assert observation2.status == "error"
    assert "Message is required" in observation2.message
