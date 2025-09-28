"""Test directory handling in individual tools."""

import os
import tempfile
from unittest.mock import Mock

import pytest

from openhands.sdk.conversation import Conversation
from openhands.tools.execute_bash.definition import BashTool
from openhands.tools.str_replace_editor.definition import FileEditorTool
from openhands.tools.task_tracker.definition import TaskTrackerTool


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    agent = Mock()
    agent.llm = Mock()
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

        tools = BashTool.create(conversation=conversation)
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

        tools = BashTool.create(working_dir=working_dir)
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

        tools = FileEditorTool.create(conversation=conversation)
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

        tools = FileEditorTool.create(workspace_root=workspace_root)
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

        tools = TaskTrackerTool.create(conversation=conversation)
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

        tools = TaskTrackerTool.create(save_dir=save_dir)
        assert len(tools) == 1
        tracker_tool = tools[0]
        # Type ignore needed for test-specific executor access
        save_dir_actual = str(tracker_tool.executor.save_dir)  # type: ignore[attr-defined]
        assert save_dir_actual == save_dir


def test_tools_without_conversation_or_explicit_params(mock_agent):
    """Test that tools work without conversation or explicit parameters."""
    with tempfile.TemporaryDirectory() as temp_dir:
        working_dir = os.path.join(temp_dir, "work")
        os.makedirs(working_dir)

        # Change to working directory for this test
        original_cwd = os.getcwd()
        os.chdir(working_dir)

        try:
            # BashTool should use current directory when no conversation or working_dir
            bash_tools = BashTool.create()
            assert len(bash_tools) == 1
            # Type ignore needed for test-specific executor access
            work_dir = bash_tools[0].executor.session.work_dir  # type: ignore[attr-defined]
            assert work_dir == working_dir

            # FileEditorTool should use current directory when no conversation
            editor_tools = FileEditorTool.create()
            assert len(editor_tools) == 1
            # Type ignore needed for test-specific executor access
            cwd = str(editor_tools[0].executor.editor._cwd)  # type: ignore[attr-defined]
            assert cwd == os.getcwd()

            # TaskTrackerTool should have None save_dir when no conversation
            tracker_tools = TaskTrackerTool.create()
            assert len(tracker_tools) == 1
            # Type ignore needed for test-specific executor access
            save_dir = tracker_tools[0].executor.save_dir  # type: ignore[attr-defined]
            assert save_dir is None

        finally:
            os.chdir(original_cwd)
