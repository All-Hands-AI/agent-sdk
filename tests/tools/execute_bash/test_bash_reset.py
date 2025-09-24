"""Tests for bash terminal reset functionality."""

import tempfile

from openhands.tools.execute_bash import (
    BashTool,
    ExecuteBashAction,
    ExecuteBashObservation,
)


def test_bash_reset_basic():
    """Test basic reset functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tools = BashTool.create(working_dir=temp_dir)
        tool = tools[0]

        # Execute a command to set an environment variable
        action = ExecuteBashAction(command="export TEST_VAR=hello")
        result = tool(action)
        assert isinstance(result, ExecuteBashObservation)
        assert result.metadata.exit_code == 0

        # Verify the variable is set
        action = ExecuteBashAction(command="echo $TEST_VAR")
        result = tool(action)
        assert isinstance(result, ExecuteBashObservation)
        assert "hello" in result.output

        # Reset the terminal
        reset_action = ExecuteBashAction(command="", reset=True)
        reset_result = tool(reset_action)
        assert isinstance(reset_result, ExecuteBashObservation)
        assert "Terminal session has been reset" in reset_result.output
        assert reset_result.command == "[RESET]"
        assert reset_result.exit_code == 0

        # Verify the variable is no longer set after reset
        action = ExecuteBashAction(command="echo $TEST_VAR")
        result = tool(action)
        assert isinstance(result, ExecuteBashObservation)
        # The variable should be empty after reset
        assert result.output.strip() == ""


def test_bash_reset_with_command():
    """Test that reset ignores the command parameter."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tools = BashTool.create(working_dir=temp_dir)
        tool = tools[0]

        # Set an environment variable
        action = ExecuteBashAction(command="export TEST_VAR=world")
        result = tool(action)
        assert isinstance(result, ExecuteBashObservation)
        assert result.metadata.exit_code == 0

        # Reset with a command (should ignore the command)
        reset_action = ExecuteBashAction(
            command="echo 'this should be ignored'", reset=True
        )
        reset_result = tool(reset_action)
        assert isinstance(reset_result, ExecuteBashObservation)
        assert "Terminal session has been reset" in reset_result.output
        assert "this should be ignored" not in reset_result.output
        assert reset_result.command == "[RESET]"

        # Verify the variable is no longer set
        action = ExecuteBashAction(command="echo $TEST_VAR")
        result = tool(action)
        assert isinstance(result, ExecuteBashObservation)
        assert result.output.strip() == ""


def test_bash_reset_working_directory():
    """Test that reset preserves the working directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tools = BashTool.create(working_dir=temp_dir)
        tool = tools[0]

        # Check initial working directory
        action = ExecuteBashAction(command="pwd")
        result = tool(action)
        assert isinstance(result, ExecuteBashObservation)
        assert temp_dir in result.output

        # Change directory
        action = ExecuteBashAction(command="cd /tmp")
        result = tool(action)
        assert isinstance(result, ExecuteBashObservation)

        # Verify directory changed
        action = ExecuteBashAction(command="pwd")
        result = tool(action)
        assert isinstance(result, ExecuteBashObservation)
        assert "/tmp" in result.output

        # Reset the terminal
        reset_action = ExecuteBashAction(command="", reset=True)
        reset_result = tool(reset_action)
        assert isinstance(reset_result, ExecuteBashObservation)
        assert "Terminal session has been reset" in reset_result.output

        # Verify working directory is back to original
        action = ExecuteBashAction(command="pwd")
        result = tool(action)
        assert isinstance(result, ExecuteBashObservation)
        assert temp_dir in result.output


def test_bash_reset_multiple_times():
    """Test that reset can be called multiple times."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tools = BashTool.create(working_dir=temp_dir)
        tool = tools[0]

        # First reset
        reset_action = ExecuteBashAction(command="", reset=True)
        reset_result = tool(reset_action)
        assert isinstance(reset_result, ExecuteBashObservation)
        assert "Terminal session has been reset" in reset_result.output

        # Execute a command after first reset
        action = ExecuteBashAction(command="echo 'after first reset'")
        result = tool(action)
        assert isinstance(result, ExecuteBashObservation)
        assert "after first reset" in result.output

        # Second reset
        reset_action = ExecuteBashAction(command="", reset=True)
        reset_result = tool(reset_action)
        assert isinstance(reset_result, ExecuteBashObservation)
        assert "Terminal session has been reset" in reset_result.output

        # Execute a command after second reset
        action = ExecuteBashAction(command="echo 'after second reset'")
        result = tool(action)
        assert isinstance(result, ExecuteBashObservation)
        assert "after second reset" in result.output


def test_bash_reset_with_timeout():
    """Test that reset works with timeout parameter."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tools = BashTool.create(working_dir=temp_dir)
        tool = tools[0]

        # Reset with timeout (should ignore timeout)
        reset_action = ExecuteBashAction(command="", reset=True, timeout=5.0)
        reset_result = tool(reset_action)
        assert isinstance(reset_result, ExecuteBashObservation)
        assert "Terminal session has been reset" in reset_result.output
        assert reset_result.command == "[RESET]"
        assert reset_result.exit_code == 0


def test_bash_reset_with_is_input():
    """Test that reset works with is_input parameter."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tools = BashTool.create(working_dir=temp_dir)
        tool = tools[0]

        # Reset with is_input (should ignore is_input)
        reset_action = ExecuteBashAction(command="", reset=True, is_input=True)
        reset_result = tool(reset_action)
        assert isinstance(reset_result, ExecuteBashObservation)
        assert "Terminal session has been reset" in reset_result.output
        assert reset_result.command == "[RESET]"
        assert reset_result.exit_code == 0
