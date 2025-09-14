"""Tests for RepomixTool subclass."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openhands.tools.repomix import (
    PackCodebaseAction,
    PackCodebaseObservation,
    RepomixTool,
)


def test_repomix_tool_initialization():
    """Test that RepomixTool initializes correctly."""
    tool = RepomixTool.create()

    # Check that the tool has the correct name and properties
    assert tool.name == "pack_codebase"
    assert tool.executor is not None
    assert tool.action_type == PackCodebaseAction


def test_repomix_tool_to_openai_tool():
    """Test that RepomixTool can be converted to OpenAI tool format."""
    tool = RepomixTool.create()

    # Convert to OpenAI tool format
    openai_tool = tool.to_openai_tool()

    # Check the format
    assert openai_tool["type"] == "function"
    assert openai_tool["function"]["name"] == "pack_codebase"
    assert "description" in openai_tool["function"]
    assert "parameters" in openai_tool["function"]


def test_pack_codebase_action_creation():
    """Test PackCodebaseAction creation with various parameters."""
    # Basic action
    action = PackCodebaseAction(directory="/test/path")
    assert action.directory == "/test/path"
    assert action.compress is False
    assert action.include_patterns is None
    assert action.ignore_patterns is None
    assert action.top_files_length == 10

    # Action with all parameters
    action = PackCodebaseAction(
        directory="/test/path",
        compress=True,
        include_patterns="**/*.py,**/*.md",
        ignore_patterns="test/**,*.log",
        top_files_length=15,
    )
    assert action.directory == "/test/path"
    assert action.compress is True
    assert action.include_patterns == "**/*.py,**/*.md"
    assert action.ignore_patterns == "test/**,*.log"
    assert action.top_files_length == 15


def test_pack_codebase_action_visualize():
    """Test PackCodebaseAction visualization."""
    action = PackCodebaseAction(
        directory="/test/path",
        compress=True,
        include_patterns="**/*.py",
        ignore_patterns="test/**",
        top_files_length=5,
    )

    visualization = action.visualize
    assert "Pack Codebase" in str(visualization)
    assert "/test/path" in str(visualization)


def test_pack_codebase_observation_success():
    """Test PackCodebaseObservation for successful operation."""
    observation = PackCodebaseObservation(
        output="<xml>packed content</xml>",
        directory="/test/path",
        output_id="test-id-123",
        error=False,
    )

    assert observation.output == "<xml>packed content</xml>"
    assert observation.directory == "/test/path"
    assert observation.output_id == "test-id-123"
    assert observation.error is False

    # Test agent observation
    agent_obs = observation.agent_observation
    assert len(agent_obs) == 1
    from openhands.sdk.llm import TextContent

    assert isinstance(agent_obs[0], TextContent)
    assert "Successfully packed codebase" in agent_obs[0].text
    assert "/test/path" in agent_obs[0].text


def test_pack_codebase_observation_error():
    """Test PackCodebaseObservation for error case."""
    observation = PackCodebaseObservation(
        output="",
        directory="/test/path",
        error=True,
        error_message="Directory not found",
    )

    assert observation.error is True
    assert observation.error_message == "Directory not found"

    # Test agent observation
    agent_obs = observation.agent_observation
    assert len(agent_obs) == 1
    from openhands.sdk.llm import TextContent

    assert isinstance(agent_obs[0], TextContent)
    assert "Error packing codebase" in agent_obs[0].text
    assert "Directory not found" in agent_obs[0].text


def test_pack_codebase_observation_visualize():
    """Test PackCodebaseObservation visualization."""
    # Success case
    observation = PackCodebaseObservation(
        output="<xml>content</xml>",
        directory="/test/path",
        error=False,
    )
    visualization = observation.visualize
    assert "Codebase Packed Successfully" in str(visualization)

    # Error case
    observation = PackCodebaseObservation(
        output="",
        directory="/test/path",
        error=True,
        error_message="Test error",
    )
    visualization = observation.visualize
    assert "Repomix Error" in str(visualization)


@patch("openhands.tools.repomix.definition.asyncio.run")
def test_repomix_executor_directory_not_found(mock_asyncio_run):
    """Test RepomixExecutor with non-existent directory."""
    from openhands.tools.repomix.definition import RepomixExecutor

    # Mock asyncio.run to return our test result
    mock_result = PackCodebaseObservation(
        output="",
        directory="/nonexistent/path",
        error=True,
        error_message="Directory does not exist: /nonexistent/path",
    )
    mock_asyncio_run.return_value = mock_result

    executor = RepomixExecutor()
    action = PackCodebaseAction(directory="/nonexistent/path")

    result = executor(action)

    assert result.error is True
    assert result.error_message is not None
    assert "Directory does not exist" in result.error_message


@patch("openhands.tools.repomix.definition.asyncio.run")
def test_repomix_executor_exception_handling(mock_asyncio_run):
    """Test RepomixExecutor exception handling."""
    from openhands.tools.repomix.definition import RepomixExecutor

    # Mock asyncio.run to raise an exception
    mock_asyncio_run.side_effect = Exception("Test exception")

    executor = RepomixExecutor()
    action = PackCodebaseAction(directory="/test/path")

    result = executor(action)

    assert result.error is True
    assert result.error_message is not None
    assert "Test exception" in result.error_message


@pytest.mark.asyncio
async def test_repomix_executor_async_success():
    """Test RepomixExecutor async implementation with mocked MCP client."""
    from openhands.tools.repomix.definition import RepomixExecutor

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test file in the directory
        test_file = Path(temp_dir) / "test.py"
        test_file.write_text("print('hello world')")

        executor = RepomixExecutor()
        action = PackCodebaseAction(directory=temp_dir)

        # Mock the MCP client and its methods
        with patch("openhands.tools.repomix.definition.MCPClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock the call_tool result
            mock_result = MagicMock()
            mock_content = MagicMock()
            mock_content.text = "<xml>mocked repomix output</xml>"
            mock_result.content = [mock_content]
            mock_client.call_tool.return_value = mock_result

            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            result = await executor._pack_codebase_async(action)

            assert result.error is False
            assert result.output == "<xml>mocked repomix output</xml>"
            assert result.directory == str(Path(temp_dir).resolve())

            # Verify MCP client was called correctly
            mock_client.call_tool.assert_called_once()
            call_args = mock_client.call_tool.call_args
            assert call_args[0][0] == "pack_codebase"
            assert "directory" in call_args[0][1]


@pytest.mark.asyncio
async def test_repomix_executor_async_with_options():
    """Test RepomixExecutor async implementation with all options."""
    from openhands.tools.repomix.definition import RepomixExecutor

    with tempfile.TemporaryDirectory() as temp_dir:
        executor = RepomixExecutor()
        action = PackCodebaseAction(
            directory=temp_dir,
            compress=True,
            include_patterns="**/*.py,**/*.md",
            ignore_patterns="test/**,*.log",
            top_files_length=15,
        )

        # Mock the MCP client
        with patch("openhands.tools.repomix.definition.MCPClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock the call_tool result
            mock_result = MagicMock()
            mock_content = MagicMock()
            mock_content.text = "<xml>compressed output</xml>"
            mock_result.content = [mock_content]
            mock_client.call_tool.return_value = mock_result

            # Mock the async context manager
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            result = await executor._pack_codebase_async(action)

            assert result.error is False
            assert result.output == "<xml>compressed output</xml>"

            # Verify all options were passed to MCP client
            call_args = mock_client.call_tool.call_args[0][1]
            assert call_args["compress"] is True
            assert call_args["includePatterns"] == "**/*.py,**/*.md"
            assert call_args["ignorePatterns"] == "test/**,*.log"
            assert call_args["topFilesLength"] == 15


def test_repomix_tool_integration():
    """Test RepomixTool integration with mocked executor."""
    from openhands.tools.repomix.definition import RepomixExecutor

    # Create a real executor but mock its __call__ method
    with patch.object(RepomixExecutor, "__call__") as mock_call:
        # Mock the executor call result
        mock_result = PackCodebaseObservation(
            output="<xml>test output</xml>",
            directory="/test/path",
            error=False,
        )
        mock_call.return_value = mock_result

        # Create tool and execute action
        tool = RepomixTool.create()
        action = PackCodebaseAction(directory="/test/path")

        result = tool.call(action)

        assert isinstance(result, PackCodebaseObservation)
        assert result.output == "<xml>test output</xml>"
        assert result.error is False

        # Verify executor was called
        mock_call.assert_called_once_with(action)
