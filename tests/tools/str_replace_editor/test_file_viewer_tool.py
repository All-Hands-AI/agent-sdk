"""Tests for FileViewerTool - read-only file viewing tool."""

import os
import tempfile
from uuid import uuid4

from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.llm import LLM
from openhands.sdk.workspace import LocalWorkspace
from openhands.tools.str_replace_editor import (
    FileViewerTool,
    StrReplaceEditorAction,
    StrReplaceEditorObservation,
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
    """Test that FileViewerTool initializes correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = FileViewerTool.create(conv_state)
        tool = tools[0]

        # Check that the tool has the correct name and properties
        assert tool.name == "file_viewer"
        assert tool.executor is not None
        assert issubclass(tool.action_type, StrReplaceEditorAction)

        # Check that it's configured as read-only
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.idempotentHint is True


def test_file_viewer_tool_view_file():
    """Test that FileViewerTool can view files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = FileViewerTool.create(conv_state)
        tool = tools[0]

        test_file = os.path.join(temp_dir, "test.txt")

        # Create a test file
        with open(test_file, "w") as f:
            f.write("Line 1\nLine 2\nLine 3")

        # Create an action to view the file
        action = StrReplaceEditorAction(command="view", path=test_file)

        # Execute the action
        result = tool(action)

        # Check the result
        assert result is not None
        assert isinstance(result, StrReplaceEditorObservation)
        assert not result.error
        assert "Line 1" in result.output
        assert "Line 2" in result.output
        assert "Line 3" in result.output


def test_file_viewer_tool_view_directory():
    """Test that FileViewerTool can view directories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = FileViewerTool.create(conv_state)
        tool = tools[0]

        # Create some test files
        test_file1 = os.path.join(temp_dir, "file1.txt")
        test_file2 = os.path.join(temp_dir, "file2.txt")

        with open(test_file1, "w") as f:
            f.write("File 1 content")
        with open(test_file2, "w") as f:
            f.write("File 2 content")

        # Create an action to view the directory
        action = StrReplaceEditorAction(command="view", path=temp_dir)

        # Execute the action
        result = tool(action)

        # Check the result
        assert result is not None
        assert isinstance(result, StrReplaceEditorObservation)
        assert not result.error
        assert "file1.txt" in result.output
        assert "file2.txt" in result.output


def test_file_viewer_tool_blocks_create():
    """Test that FileViewerTool blocks create operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = FileViewerTool.create(conv_state)
        tool = tools[0]

        test_file = os.path.join(temp_dir, "test.txt")

        # Create an action to create a file (should be blocked)
        action = StrReplaceEditorAction(
            command="create",
            path=test_file,
            file_text="Hello, World!",
        )

        # Execute the action
        result = tool(action)

        # Check that it was blocked
        assert result is not None
        assert isinstance(result, StrReplaceEditorObservation)
        assert result.error is not None
        assert "not allowed in read-only mode" in result.error
        assert not os.path.exists(test_file)


def test_file_viewer_tool_blocks_str_replace():
    """Test that FileViewerTool blocks str_replace operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = FileViewerTool.create(conv_state)
        tool = tools[0]

        test_file = os.path.join(temp_dir, "test.txt")

        # Create a test file first
        with open(test_file, "w") as f:
            f.write("Hello, World!\nThis is a test.")

        # Create an action to replace text (should be blocked)
        action = StrReplaceEditorAction(
            command="str_replace",
            path=test_file,
            old_str="World",
            new_str="Universe",
        )

        # Execute the action
        result = tool(action)

        # Check that it was blocked
        assert result is not None
        assert isinstance(result, StrReplaceEditorObservation)
        assert result.error is not None
        assert "not allowed in read-only mode" in result.error

        # Check that file content wasn't changed
        with open(test_file) as f:
            content = f.read()
        assert "Hello, World!" in content
        assert "Universe" not in content


def test_file_viewer_tool_to_openai_tool():
    """Test that FileViewerTool can be converted to OpenAI tool format."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = FileViewerTool.create(conv_state)
        tool = tools[0]

        # Convert to OpenAI tool format
        openai_tool = tool.to_openai_tool()

        # Check the format
        assert openai_tool["type"] == "function"
        assert openai_tool["function"]["name"] == "file_viewer"
        assert "description" in openai_tool["function"]
        assert "parameters" in openai_tool["function"]


def test_file_viewer_tool_includes_working_directory_in_description():
    """Test that FileViewerTool includes working directory info in description."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = FileViewerTool.create(conv_state)
        tool = tools[0]

        # Check that the tool description includes working directory information
        assert f"Your current working directory is: {temp_dir}" in tool.description
        assert (
            "When exploring project structure, start with this directory "
            "instead of the root filesystem."
        ) in tool.description

        # Verify the original description is still there
        assert "Custom tool for viewing files in plain-text format" in tool.description


def test_file_viewer_tool_openai_format_includes_working_directory():
    """Test that OpenAI tool format includes working directory info."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = FileViewerTool.create(conv_state)
        tool = tools[0]

        # Convert to OpenAI tool format
        openai_tool = tool.to_openai_tool()

        # Check that the description includes working directory information
        function_def = openai_tool["function"]
        assert "description" in function_def
        description = function_def["description"]
        assert f"Your current working directory is: {temp_dir}" in description
        assert (
            "When exploring project structure, start with this directory "
            "instead of the root filesystem."
        ) in description
