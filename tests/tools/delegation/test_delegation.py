"""Tests for delegation tools."""

import uuid
from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.llm import LLM, TextContent
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
    parent_conversation.state.workspace.working_dir = "/tmp"
    parent_conversation.visualize = False

    executor = DelegateExecutor()

    return executor, parent_conversation


def create_mock_conversation():
    """Helper to create a mock conversation."""
    mock_conv = MagicMock()
    mock_conv.id = str(uuid.uuid4())
    mock_conv.state.agent_status = AgentExecutionStatus.FINISHED
    return mock_conv


def test_delegate_action_creation():
    """Test creating DelegateAction instances."""
    # Test spawn action
    spawn_action = DelegateAction(command="spawn", ids=["agent1", "agent2"])
    assert spawn_action.command == "spawn"
    assert spawn_action.ids == ["agent1", "agent2"]
    assert spawn_action.tasks is None

    # Test delegate action
    delegate_action = DelegateAction(
        command="delegate",
        tasks={"agent1": "Analyze code quality", "agent2": "Write tests"},
    )
    assert delegate_action.command == "delegate"
    assert delegate_action.tasks == {
        "agent1": "Analyze code quality",
        "agent2": "Write tests",
    }
    assert delegate_action.ids is None


def test_delegate_observation_creation():
    """Test creating DelegateObservation instances."""
    # Test spawn observation
    spawn_observation = DelegateObservation(
        command="spawn",
        output=[TextContent(text="spawn: Sub-agents created successfully")],
    )
    assert len(spawn_observation.output) == 1
    assert isinstance(spawn_observation.output[0], TextContent)
    assert spawn_observation.output[0].text == "spawn: Sub-agents created successfully"
    # spawn observation doesn't have results field anymore

    # Test delegate observation
    delegate_observation = DelegateObservation(
        command="delegate",
        output=[
            TextContent(
                text=(
                    "delegate: Tasks completed successfully\n\nResults:\n"
                    "1. Result 1\n2. Result 2"
                )
            )
        ],
    )
    assert len(delegate_observation.output) == 1
    output_block = delegate_observation.output[0]
    assert isinstance(output_block, TextContent)
    assert "Tasks completed successfully" in output_block.text
    assert "Result 1" in output_block.text
    assert "Result 2" in output_block.text


def test_delegate_executor_delegate():
    """Test DelegateExecutor delegate operation."""
    executor, parent_conversation = create_test_executor_and_parent()

    # First spawn some agents
    spawn_action = DelegateAction(command="spawn", ids=["agent1", "agent2"])
    spawn_observation = executor(spawn_action, parent_conversation)
    output_block = spawn_observation.output[0]
    assert isinstance(output_block, TextContent)
    assert "Successfully spawned" in output_block.text

    # Then delegate tasks to them
    delegate_action = DelegateAction(
        command="delegate",
        tasks={"agent1": "Analyze code quality", "agent2": "Write tests"},
    )

    with patch.object(executor, "_delegate_tasks") as mock_delegate:
        mock_observation = DelegateObservation(
            command="delegate",
            output=[
                TextContent(
                    text=(
                        "delegate: Tasks completed successfully\n\nResults:\n"
                        "1. Agent agent1: Code analysis complete\n"
                        "2. Agent agent2: Tests written"
                    )
                )
            ],
        )
        mock_delegate.return_value = mock_observation

        observation = executor(delegate_action, parent_conversation)

    assert isinstance(observation, DelegateObservation)
    obs_block = observation.output[0]
    assert isinstance(obs_block, TextContent)
    assert "Agent agent1: Code analysis complete" in obs_block.text
    assert "Agent agent2: Tests written" in obs_block.text


def test_delegate_executor_missing_task():
    """Test DelegateExecutor delegate with empty tasks dict."""
    executor, parent_conversation = create_test_executor_and_parent()

    # Test delegate action with no tasks
    action = DelegateAction(command="delegate", tasks={})

    observation = executor(action, parent_conversation)

    assert isinstance(observation, DelegateObservation)
    # Error message should be in the error field
    assert observation.has_error
    assert observation.error is not None
    assert (
        "task is required" in observation.error.lower()
        or "at least one task" in observation.error.lower()
    )


def test_delegation_manager_init():
    """Test DelegateExecutor initialization."""
    mock_conv = create_mock_conversation()
    manager = DelegateExecutor()

    manager._parent_conversation = mock_conv

    # Test that we can access the parent conversation
    assert manager.parent_conversation == mock_conv
    assert str(manager.parent_conversation.id) == str(mock_conv.id)

    # Test that sub-agents dict is empty initially
    assert len(manager._sub_agents) == 0
