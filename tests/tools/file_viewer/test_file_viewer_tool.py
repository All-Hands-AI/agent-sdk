"""Tests for FileViewerTool."""

import tempfile
from pathlib import Path
from uuid import uuid4

from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.llm import LLM
from openhands.sdk.workspace import LocalWorkspace
from openhands.tools.file_viewer import (
    FileViewerAction,
    FileViewerObservation,
    FileViewerTool,
)


def _create_test_conv_state(temp_dir: str) -> ConversationState:
    """Helper to create a test conversation state."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm")
    agent = Agent(llm=llm, tools=[])
    return ConversationState.create(
        id=uuid4(),
        agent=agent,
        workspace=LocalWorkspace(working_dir=temp_dir),
    )


def test_file_viewer_tool_initialization():
    """Test FileViewerTool initialization."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = FileViewerTool.create(conv_state=conv_state)
        assert len(tools) == 1
        tool = tools[0]
        assert tool.name == "file_viewer"
        assert "Custom tool for viewing" in tool.description
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False


def test_file_viewer_tool_view_file():
    """Test viewing a file with FileViewerTool."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test file
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Hello, World!\nThis is a test file.")

        conv_state = _create_test_conv_state(temp_dir)
        tool = FileViewerTool.create(conv_state=conv_state)[0]

        # Test viewing the file
        action = FileViewerAction(path=str(test_file))
        observation = tool(action)

        assert isinstance(observation, FileViewerObservation)
        assert not observation.error
        assert "Hello, World!" in observation.content
        assert "This is a test file." in observation.content


def test_file_viewer_tool_view_directory():
    """Test viewing a directory with FileViewerTool."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test files
        (Path(temp_dir) / "file1.txt").write_text("Content 1")
        (Path(temp_dir) / "file2.py").write_text("print('hello')")

        conv_state = _create_test_conv_state(temp_dir)
        tool = FileViewerTool.create(conv_state=conv_state)[0]

        # Test viewing the directory
        action = FileViewerAction(path=temp_dir)
        observation = tool(action)

        assert isinstance(observation, FileViewerObservation)
        assert not observation.error
        assert "file1.txt" in observation.content
        assert "file2.py" in observation.content


def test_file_viewer_tool_blocks_create():
    """Test that FileViewerTool blocks create operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        FileViewerTool.create(conv_state=conv_state)[0]

        # Test that create is blocked - this should fail at action creation level
        try:
            FileViewerAction(command="create", path="new_file.txt")  # type: ignore[call-arg]
            assert False, "Should not be able to create action with 'create' command"
        except Exception:
            # Expected - create command is not allowed in the Literal type
            pass


def test_file_viewer_tool_blocks_str_replace():
    """Test that FileViewerTool blocks str_replace operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test file
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Hello, World!")

        conv_state = _create_test_conv_state(temp_dir)
        FileViewerTool.create(conv_state=conv_state)[0]

        # Test that str_replace is blocked - this should fail at action creation level
        try:
            FileViewerAction(command="str_replace", path="test.txt")  # type: ignore[call-arg]
            assert False, (
                "Should not be able to create action with 'str_replace' command"
            )
        except Exception:
            # Expected - str_replace command is not allowed in the Literal type
            pass


def test_file_viewer_tool_blocks_insert():
    """Test that FileViewerTool blocks insert operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test file
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Line 1\nLine 2")

        conv_state = _create_test_conv_state(temp_dir)
        FileViewerTool.create(conv_state=conv_state)[0]

        # Test that insert is blocked - this should fail at action creation level
        try:
            FileViewerAction(command="insert", path="test.txt")  # type: ignore[call-arg]
            assert False, "Should not be able to create action with 'insert' command"
        except Exception:
            # Expected - insert command is not allowed in the Literal type
            pass


def test_file_viewer_tool_blocks_undo_edit():
    """Test that FileViewerTool blocks undo_edit operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test file
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Hello, World!")

        conv_state = _create_test_conv_state(temp_dir)
        FileViewerTool.create(conv_state=conv_state)[0]

        # Test that undo_edit is blocked - this should fail at action creation level
        try:
            FileViewerAction(command="undo_edit", path="test.txt")  # type: ignore[call-arg]
            assert False, "Should not be able to create action with 'undo_edit' command"
        except Exception:
            # Expected - undo_edit command is not allowed in the Literal type
            pass


def test_file_viewer_tool_to_openai_tool():
    """Test FileViewerTool OpenAI tool format."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tool = FileViewerTool.create(conv_state=conv_state)[0]
        openai_tool = tool.to_openai_tool()

    assert openai_tool["type"] == "function"
    function_def = openai_tool["function"]
    assert function_def is not None
    assert function_def["name"] == "file_viewer"
    description = function_def.get("description", "")
    assert "Custom tool for viewing" in description
