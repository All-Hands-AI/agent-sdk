"""Tests for delegation tools."""

import uuid
from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from openhands.sdk.delegation.manager import DelegationManager
from openhands.sdk.llm import LLM
from openhands.tools.delegation.definition import DelegateAction, DelegateObservation
from openhands.tools.delegation.impl import DelegateExecutor


def create_test_executor_and_parent():
    """Helper to create test executor and parent conversation."""
    # Create delegation manager
    delegation_manager = DelegationManager()
    executor = DelegateExecutor(delegation_manager)

    # Create a real LLM object
    llm = LLM(
        model="openai/gpt-4o",
        api_key=SecretStr("test-key"),
        base_url="https://api.openai.com/v1",
    )

    # Create a mock parent conversation
    parent_conversation = MagicMock()
    parent_conversation.id = uuid.uuid4()
    parent_conversation.agent.llm = llm
    parent_conversation.agent.cli_mode = True
    parent_conversation.state.workspace = "/tmp"
    parent_conversation.visualize = False  # Disable visualization for tests

    # Register the parent conversation
    delegation_manager.register_conversation(parent_conversation)

    return executor, parent_conversation, delegation_manager


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
    executor, parent_conversation, _ = create_test_executor_and_parent()

    # Create spawn action with conversation_id
    action = DelegateAction(operation="spawn", task="Analyze code quality")
    action = action.model_copy(update={"conversation_id": parent_conversation.id})

    # Mock threading.Thread to avoid spawning real threads
    with patch("threading.Thread") as mock_thread:
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Execute action
        observation = executor(action)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.sub_conversation_id is not None
    assert observation.status == "created"
    assert "Sub-agent" in observation.message and (
        "created" in observation.message
        or "running" in observation.message
        or "asynchronously" in observation.message
    )
    assert (
        observation.result is not None
        and "Task assigned: Analyze code quality" in observation.result
    )


def test_delegate_executor_send():
    """Test DelegateExecutor send operation."""
    executor, parent_conversation, _ = create_test_executor_and_parent()

    # Mock threading.Thread to avoid spawning real threads
    with patch("threading.Thread") as mock_thread:
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # First spawn a sub-agent
        spawn_action = DelegateAction(operation="spawn", task="Test task")
        spawn_action = spawn_action.model_copy(
            update={"conversation_id": parent_conversation.id}
        )
        spawn_result = executor(spawn_action)
        sub_id = spawn_result.sub_conversation_id

    # Send message to sub-agent (use executor.delegation_manager
    # to send to mock conversation)
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
    executor, parent_conversation, _ = create_test_executor_and_parent()

    # Mock threading.Thread to avoid spawning real threads
    with patch("threading.Thread") as mock_thread:
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # First spawn a sub-agent
        spawn_action = DelegateAction(operation="spawn", task="Test task")
        spawn_action = spawn_action.model_copy(
            update={"conversation_id": parent_conversation.id}
        )
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
