"""Tests for delegation tools."""

import uuid
from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from openhands.sdk.llm import LLM
from openhands.tools.delegate import (
    DelegateAction,
    DelegateExecutor,
    DelegateObservation,
)


def create_test_executor_and_parent():
    """Helper to create test executor and parent conversation."""
    # Create executor (singleton pattern)
    executor = DelegateExecutor()

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
    executor.register_conversation(parent_conversation)

    return executor, parent_conversation


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
        operation="spawn",
        success=True,
        sub_conversation_id="sub-123",
        message="Sub-agent created successfully",
    )
    assert observation.sub_conversation_id == "sub-123"
    assert observation.operation == "spawn"
    assert observation.success is True
    assert observation.message == "Sub-agent created successfully"


def test_delegate_executor_spawn():
    """Test DelegateExecutor spawn operation."""
    executor, parent_conversation = create_test_executor_and_parent()

    # Create spawn action with conversation_id
    action = DelegateAction(operation="spawn", task="Analyze code quality")
    action = action.model_copy(update={"conversation_id": parent_conversation.id})

    # Mock the executor's private _spawn_sub_agent method
    with patch.object(executor, "_spawn_sub_agent") as mock_spawn:
        mock_observation = DelegateObservation(
            operation="spawn",
            success=True,
            message="Sub-agent created successfully",
            sub_conversation_id="sub-123",
        )
        mock_spawn.return_value = mock_observation

        # Execute action
        observation = executor(action, parent_conversation)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.sub_conversation_id is not None
    assert observation.success is True
    assert "Sub-agent" in observation.message and (
        "created" in observation.message
        or "running" in observation.message
        or "asynchronously" in observation.message
    )


def test_delegate_executor_send():
    """Test DelegateExecutor send operation."""
    executor, parent_conversation = create_test_executor_and_parent()

    # Mock the executor's private methods
    with (
        patch.object(executor, "_spawn_sub_agent") as mock_spawn,
        patch.object(executor, "_send_to_sub_agent") as mock_send,
    ):
        # First spawn a sub-agent
        sub_id = "sub-123"
        mock_spawn.return_value = DelegateObservation(
            operation="spawn",
            success=True,
            message="Sub-agent created",
            sub_conversation_id=sub_id,
        )
        spawn_action = DelegateAction(operation="spawn", task="Test task")
        spawn_action = spawn_action.model_copy(
            update={"conversation_id": parent_conversation.id}
        )
        spawn_result = executor(spawn_action, parent_conversation)
        sub_id = spawn_result.sub_conversation_id

        # Mock send to return success observation
        mock_send.return_value = DelegateObservation(
            operation="send",
            success=True,
            sub_conversation_id=sub_id,
            message=f"Message sent to sub-agent {sub_id}",
        )

        # Send message to sub-agent
        send_action = DelegateAction(
            operation="send", sub_conversation_id=sub_id, message="Hello sub-agent"
        )
        observation = executor(send_action, None)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.sub_conversation_id == sub_id
    assert observation.success is True
    assert f"Message sent to sub-agent {sub_id}" in observation.message


def test_delegate_executor_send_invalid_id():
    """Test DelegateExecutor send with invalid sub-agent ID."""
    executor = DelegateExecutor()

    # Send message to non-existent sub-agent
    action = DelegateAction(
        operation="send", sub_conversation_id="invalid-id", message="Hello"
    )
    observation = executor(action, None)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.success is False
    assert "Failed to send message" in observation.message


def test_delegate_executor_close():
    """Test DelegateExecutor close operation."""
    executor, parent_conversation = create_test_executor_and_parent()

    # Mock the executor's private methods
    with (
        patch.object(executor, "_spawn_sub_agent") as mock_spawn,
        patch.object(executor, "_close_sub_agent") as mock_close,
    ):
        # First spawn a sub-agent
        sub_id = "sub-123"
        mock_spawn.return_value = DelegateObservation(
            operation="spawn",
            success=True,
            message="Sub-agent created",
            sub_conversation_id=sub_id,
        )
        spawn_action = DelegateAction(operation="spawn", task="Test task")
        spawn_action = spawn_action.model_copy(
            update={"conversation_id": parent_conversation.id}
        )
        spawn_result = executor(spawn_action, parent_conversation)
        sub_id = spawn_result.sub_conversation_id

        # Mock close to return success observation
        mock_close.return_value = DelegateObservation(
            operation="close",
            success=True,
            sub_conversation_id=sub_id,
            message=f"Sub-agent {sub_id} closed successfully",
        )

        # Close the sub-agent
        close_action = DelegateAction(operation="close", sub_conversation_id=sub_id)
        observation = executor(close_action, None)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.sub_conversation_id == sub_id
    assert observation.success is True
    assert f"Sub-agent {sub_id} closed successfully" in observation.message


def test_delegate_executor_spawn_missing_task():
    """Test DelegateExecutor spawn without task."""
    executor = DelegateExecutor()

    # Create spawn action without task
    action = DelegateAction(operation="spawn")

    # Execute action
    observation = executor(action, None)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.success is False
    assert "Task is required for spawn operation" in observation.message


def test_delegate_executor_send_missing_params():
    """Test DelegateExecutor send with missing parameters."""
    executor = DelegateExecutor()

    # Test missing sub_conversation_id
    action1 = DelegateAction(operation="send", message="Hello")
    observation1 = executor(action1, None)
    assert observation1.success is False
    assert "Sub-conversation ID is required" in observation1.message

    # Test missing message
    action2 = DelegateAction(operation="send", sub_conversation_id="sub-123")
    observation2 = executor(action2, None)
    assert observation2.success is False
    assert "Message is required" in observation2.message
