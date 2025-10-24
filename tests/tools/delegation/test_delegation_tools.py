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

    # Create executor with parent conversation (auto-registered in __init__)
    executor = DelegateExecutor(parent_conversation)

    return executor, parent_conversation


def test_delegate_action_creation():
    """Test creating DelegateAction instances."""
    # Test delegate action
    delegate_action = DelegateAction(task="Analyze code quality")
    assert delegate_action.task == "Analyze code quality"


def test_delegate_observation_creation():
    """Test creating DelegateObservation instances."""
    observation = DelegateObservation(
        success=True,
        sub_conversation_id="sub-123",
        message="Sub-agent created successfully",
    )
    assert observation.sub_conversation_id == "sub-123"
    assert observation.success is True
    assert observation.message == "Sub-agent created successfully"


def test_delegate_executor_delegate():
    """Test DelegateExecutor delegate operation."""
    executor, parent_conversation = create_test_executor_and_parent()

    # Create delegate action with conversation_id
    action = DelegateAction(task="Analyze code quality")
    action = action.model_copy(update={"conversation_id": parent_conversation.id})

    # Mock the executor's private _delegate_task method
    with patch.object(executor, "_delegate_task") as mock_delegate:
        mock_observation = DelegateObservation(
            success=True,
            message="Sub-agent created successfully",
            sub_conversation_id="sub-123",
        )
        mock_delegate.return_value = mock_observation

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


def test_delegate_executor_missing_task():
    """Test DelegateExecutor delegate with empty task string."""
    executor, parent_conversation = create_test_executor_and_parent()

    # Create delegate action with empty task
    action = DelegateAction(task="")

    # Execute action
    observation = executor(action, parent_conversation)

    # Verify
    assert isinstance(observation, DelegateObservation)
    assert observation.success is False
    assert (
        "Task is required" in observation.message
        or "task" in observation.message.lower()
    )
