"""Tests for delegation tools."""

import uuid
from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.llm import LLM
from openhands.tools.delegate import (
    DelegateAction,
    DelegateExecutor,
    DelegateObservation,
)


def create_test_executor_and_parent():
    """Helper to create test executor and parent conversation."""
    llm = LLM(
        model="openai/gpt-4o",
        api_key=SecretStr("test-key"),
        base_url="https://api.openai.com/v1",
    )

    parent_conversation = MagicMock()
    parent_conversation.id = uuid.uuid4()
    parent_conversation.agent.llm = llm
    parent_conversation.agent.cli_mode = True
    parent_conversation.state.workspace = "/tmp"
    parent_conversation.visualize = False

    executor = DelegateExecutor(parent_conversation)

    return executor, parent_conversation


def create_mock_conversation():
    """Helper to create a mock conversation."""
    mock_conv = MagicMock()
    mock_conv.id = str(uuid.uuid4())
    mock_conv.state.agent_status = AgentExecutionStatus.FINISHED
    return mock_conv


def test_delegate_action_creation():
    """Test creating DelegateAction instances."""
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

    action = DelegateAction(task="Analyze code quality")
    action = action.model_copy(update={"conversation_id": parent_conversation.id})

    with patch.object(executor, "_delegate_task") as mock_delegate:
        mock_observation = DelegateObservation(
            success=True,
            message="Sub-agent created successfully",
            sub_conversation_id="sub-123",
        )
        mock_delegate.return_value = mock_observation

        observation = executor(action, parent_conversation)

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

    action = DelegateAction(task="")

    observation = executor(action, parent_conversation)

    assert isinstance(observation, DelegateObservation)
    assert observation.success is False
    assert (
        "Task is required" in observation.message
        or "task" in observation.message.lower()
    )


def test_delegation_manager_init():
    """Test DelegateExecutor initialization."""
    mock_conv = create_mock_conversation()
    manager = DelegateExecutor()

    manager._parent_conversation = mock_conv

    assert not manager.is_task_in_progress()

    assert manager.parent_conversation == mock_conv
    assert str(manager.parent_conversation.id) == str(mock_conv.id)
