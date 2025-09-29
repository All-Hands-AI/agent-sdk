"""Test directory handling in individual tools."""

import os
import tempfile
import uuid

import pytest
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.llm import LLM
from openhands.tools.execute_bash.definition import BashTool
from openhands.tools.str_replace_editor.definition import FileEditorTool
from openhands.tools.task_tracker.definition import TaskTrackerTool


@pytest.fixture
def mock_agent():
    """Create a real agent for testing."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[])
    return agent


def test_bash_tool_with_conversation_working_dir(mock_agent):
    """Test that BashTool uses working_dir from conversation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        working_dir = os.path.join(temp_dir, "work")
        persistence_dir = os.path.join(temp_dir, "persist")
        os.makedirs(working_dir)
        os.makedirs(persistence_dir)

        conversation = Conversation(
            agent=mock_agent,
            persistence_dir=persistence_dir,
            working_dir=working_dir,
        )

        tools = BashTool.create(conversation.state)
        assert len(tools) == 1
        bash_tool = tools[0]
        # Type ignore needed for test-specific executor access
        work_dir = bash_tool.executor.session.work_dir  # type: ignore[attr-defined]
        assert work_dir == working_dir


def test_bash_tool_with_explicit_working_dir(mock_agent):
    """Test that BashTool uses explicit working_dir parameter."""
    with tempfile.TemporaryDirectory() as temp_dir:
        working_dir = os.path.join(temp_dir, "work")
        os.makedirs(working_dir)

        # Create a conversation state with the working directory
        from openhands.sdk.conversation.state import ConversationState

        conv_state = ConversationState.create(
            id=uuid.uuid4(), agent=mock_agent, working_dir=working_dir
        )

        tools = BashTool.create(conv_state)
        assert len(tools) == 1
        bash_tool = tools[0]
        # Type ignore needed for test-specific executor access
        work_dir = bash_tool.executor.session.work_dir  # type: ignore[attr-defined]
        assert work_dir == working_dir


def test_file_editor_tool_with_conversation_working_dir(mock_agent):
    """Test that FileEditorTool uses working_dir from conversation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        working_dir = os.path.join(temp_dir, "work")
        persistence_dir = os.path.join(temp_dir, "persist")
        os.makedirs(working_dir)
        os.makedirs(persistence_dir)

        conversation = Conversation(
            agent=mock_agent,
            persistence_dir=persistence_dir,
            working_dir=working_dir,
        )

        tools = FileEditorTool.create(conversation.state)
        assert len(tools) == 1
        editor_tool = tools[0]
        # Type ignore needed for test-specific executor access
        cwd = str(editor_tool.executor.editor._cwd)  # type: ignore[attr-defined]
        assert cwd == working_dir


def test_file_editor_tool_with_explicit_workspace_root(mock_agent):
    """Test that FileEditorTool uses explicit workspace_root parameter."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace_root = os.path.join(temp_dir, "workspace")
        os.makedirs(workspace_root)

        # Create a conversation state with the workspace root as working directory
        from openhands.sdk.conversation.state import ConversationState

        conv_state = ConversationState.create(
            id=uuid.uuid4(), agent=mock_agent, working_dir=workspace_root
        )
        tools = FileEditorTool.create(conv_state)
        assert len(tools) == 1
        editor_tool = tools[0]
        # Type ignore needed for test-specific executor access
        cwd = str(editor_tool.executor.editor._cwd)  # type: ignore[attr-defined]
        assert cwd == workspace_root


def test_task_tracker_tool_with_conversation_persistence_dir(mock_agent):
    """Test that TaskTrackerTool uses persistence_dir from conversation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        working_dir = os.path.join(temp_dir, "work")
        persistence_dir = os.path.join(temp_dir, "persist")
        os.makedirs(working_dir)
        os.makedirs(persistence_dir)

        conversation = Conversation(
            agent=mock_agent,
            persistence_dir=persistence_dir,
            working_dir=working_dir,
        )

        tools = TaskTrackerTool.create(conversation.state)
        assert len(tools) == 1
        tracker_tool = tools[0]
        # Type ignore needed for test-specific executor access
        save_dir = str(tracker_tool.executor.save_dir)  # type: ignore[attr-defined]
        assert save_dir == persistence_dir


def test_task_tracker_tool_with_explicit_save_dir(mock_agent):
    """Test that TaskTrackerTool uses explicit save_dir parameter."""
    with tempfile.TemporaryDirectory() as temp_dir:
        save_dir = os.path.join(temp_dir, "save")
        os.makedirs(save_dir)

        # Create a conversation state with the save directory as persistence directory
        from openhands.sdk.conversation.state import ConversationState

        conv_state = ConversationState.create(
            id=uuid.uuid4(),
            agent=mock_agent,
            persistence_dir=save_dir,
            working_dir="/tmp",
        )
        tools = TaskTrackerTool.create(conv_state)
        assert len(tools) == 1
        tracker_tool = tools[0]
        # Type ignore needed for test-specific executor access
        save_dir_actual = str(tracker_tool.executor.save_dir)  # type: ignore[attr-defined]
        assert save_dir_actual == save_dir


def test_tools_with_minimal_conversation_state(mock_agent):
    """Test that tools work with minimal conversation state."""
    with tempfile.TemporaryDirectory() as temp_dir:
        working_dir = os.path.join(temp_dir, "work")
        os.makedirs(working_dir)

        # Create minimal conversation state
        from openhands.sdk.conversation.state import ConversationState

        conv_state = ConversationState.create(
            id=uuid.uuid4(), agent=mock_agent, working_dir=working_dir
        )

        # BashTool should use working directory from conversation state
        bash_tools = BashTool.create(conv_state)
        assert len(bash_tools) == 1
        # Type ignore needed for test-specific executor access
        work_dir = bash_tools[0].executor.session.work_dir  # type: ignore[attr-defined]
        assert work_dir == working_dir

        # FileEditorTool should use working directory from conversation state
        editor_tools = FileEditorTool.create(conv_state)
        assert len(editor_tools) == 1
        # Type ignore needed for test-specific executor access
        cwd = str(editor_tools[0].executor.editor._cwd)  # type: ignore[attr-defined]
        assert cwd == working_dir

        # TaskTrackerTool should use conversation state for persistence
        tracker_tools = TaskTrackerTool.create(conv_state)
        assert len(tracker_tools) == 1
        # Type ignore needed for test-specific executor access
        save_dir = tracker_tools[0].executor.save_dir  # type: ignore[attr-defined]
        # Should use conversation ID subdirectory in persistence_dir
        assert str(conv_state.id) in str(save_dir)
