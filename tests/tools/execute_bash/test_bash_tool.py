"""Tests for BashTool subclass."""

import tempfile

from openhands.tools import BashTool
from openhands.tools.execute_bash import ExecuteBashAction, ExecuteBashObservation


def test_bash_tool_initialization():
    """Test that BashTool initializes correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tool = BashTool.create(working_dir=temp_dir)

        # Check that the tool has the correct name and properties
        assert tool.name == "execute_bash"
        assert tool.executor is not None
        assert tool.action_type == ExecuteBashAction


def test_bash_tool_with_username():
    """Test that BashTool initializes correctly with username."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tool = BashTool.create(working_dir=temp_dir, username="testuser")

        # Check that the tool has the correct name and properties
        assert tool.name == "execute_bash"
        assert tool.executor is not None
        assert tool.action_type == ExecuteBashAction


def test_bash_tool_execution():
    """Test that BashTool can execute commands."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tool = BashTool.create(working_dir=temp_dir)

        # Create an action
        action = ExecuteBashAction(command="echo 'Hello, World!'")

        # Execute the action
        result = tool(action)

        # Check the result
        assert result is not None
        assert isinstance(result, ExecuteBashObservation)
        assert "Hello, World!" in result.output


def test_bash_tool_working_directory():
    """Test that BashTool respects the working directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tool = BashTool.create(working_dir=temp_dir)

        # Create an action to check current directory
        action = ExecuteBashAction(command="pwd")

        # Execute the action
        result = tool(action)

        # Check that the working directory is correct
        assert isinstance(result, ExecuteBashObservation)
        assert temp_dir in result.output


def test_bash_tool_to_openai_tool():
    """Test that BashTool can be converted to OpenAI tool format."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tool = BashTool.create(working_dir=temp_dir)

        # Convert to OpenAI tool format
        openai_tool = tool.to_openai_tool()

        # Check the format
        assert openai_tool["type"] == "function"
        assert openai_tool["function"]["name"] == "execute_bash"
        assert "description" in openai_tool["function"]
        assert "parameters" in openai_tool["function"]
