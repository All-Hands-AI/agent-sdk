"""Tests for MCP tool functionality with new simplified implementation."""

from typing import cast
from unittest.mock import MagicMock

import mcp.types
import pytest

from openhands.sdk.llm import TextContent
from openhands.sdk.mcp.client import MCPClient
from openhands.sdk.mcp.definition import MCPToolObservation
from openhands.sdk.mcp.tool import MCPTool, MCPToolExecutor
from openhands.sdk.tool import ToolAnnotations


class MockMCPClient(MCPClient):
    """Mock MCPClient for testing that bypasses the complex constructor."""

    def __init__(self):
        # Skip the parent constructor to avoid needing transport
        pass


class TestMCPToolObservation:
    """Test MCPToolObservation functionality."""

    def test_from_call_tool_result_success(self):
        """Test creating observation from successful MCP result."""
        # Create mock MCP result
        result = MagicMock(spec=mcp.types.CallToolResult)
        result.content = [
            mcp.types.TextContent(type="text", text="Operation completed successfully")
        ]
        result.isError = False

        observation = MCPToolObservation.from_call_tool_result(
            tool_name="test_tool", result=result
        )

        assert observation.tool_name == "test_tool"
        assert len(observation.content) == 1
        assert isinstance(observation.content[0], TextContent)
        assert observation.content[0].text == "Operation completed successfully"
        assert observation.is_error is False

    def test_from_call_tool_result_error(self):
        """Test creating observation from error MCP result."""
        # Create mock MCP result
        result = MagicMock(spec=mcp.types.CallToolResult)
        result.content = [mcp.types.TextContent(type="text", text="Operation failed")]
        result.isError = True

        observation = MCPToolObservation.from_call_tool_result(
            tool_name="test_tool", result=result
        )

        assert observation.tool_name == "test_tool"
        assert len(observation.content) == 1
        assert isinstance(observation.content[0], TextContent)
        assert observation.content[0].text == "Operation failed"
        assert observation.is_error is True

    def test_from_call_tool_result_with_image(self):
        """Test creating observation from MCP result with image content."""
        # Create mock MCP result with image
        result = MagicMock(spec=mcp.types.CallToolResult)
        result.content = [
            mcp.types.TextContent(type="text", text="Here's the image:"),
            mcp.types.ImageContent(
                type="image", data="base64data", mimeType="image/png"
            ),
        ]
        result.isError = False

        observation = MCPToolObservation.from_call_tool_result(
            tool_name="test_tool", result=result
        )

        assert observation.tool_name == "test_tool"
        assert len(observation.content) == 2
        assert isinstance(observation.content[0], TextContent)
        assert observation.content[0].text == "Here's the image:"
        # Second content should be ImageContent
        assert hasattr(observation.content[1], "image_urls")
        assert observation.is_error is False

    def test_agent_observation_success(self):
        """Test agent observation formatting for success."""
        observation = MCPToolObservation(
            tool_name="test_tool",
            content=[TextContent(text="Success result")],
            is_error=False,
        )

        agent_obs = observation.agent_observation
        assert len(agent_obs) == 2
        assert isinstance(agent_obs[0], TextContent)
        assert "[Tool 'test_tool' executed.]" in agent_obs[0].text
        assert "[An error occurred during execution.]" not in agent_obs[0].text
        assert isinstance(agent_obs[1], TextContent)
        assert agent_obs[1].text == "Success result"

    def test_agent_observation_error(self):
        """Test agent observation formatting for error."""
        observation = MCPToolObservation(
            tool_name="test_tool",
            content=[TextContent(text="Error occurred")],
            is_error=True,
        )

        agent_obs = observation.agent_observation
        assert len(agent_obs) == 2
        assert isinstance(agent_obs[0], TextContent)
        assert isinstance(agent_obs[1], TextContent)
        assert "[Tool 'test_tool' executed.]" in agent_obs[0].text
        assert "[An error occurred during execution.]" in agent_obs[0].text
        assert agent_obs[1].text == "Error occurred"


class TestMCPToolExecutor:
    """Test MCPToolExecutor functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.executor = MCPToolExecutor(tool_name="test_tool", client=self.mock_client)

    def test_call_tool_success(self):
        """Test successful tool execution."""
        # Mock successful MCP call
        mock_result = MagicMock(spec=mcp.types.CallToolResult)
        mock_result.content = [
            mcp.types.TextContent(type="text", text="Success result")
        ]
        mock_result.isError = False

        # Mock action
        mock_action = MagicMock()
        mock_action.model_dump.return_value = {"param": "value"}

        # Mock call_async_from_sync to return the expected observation
        def mock_call_async_from_sync(coro_func, **kwargs):
            return MCPToolObservation.from_call_tool_result(
                tool_name="test_tool", result=mock_result
            )

        self.mock_client.call_async_from_sync = mock_call_async_from_sync

        observation = self.executor(mock_action)

        assert isinstance(observation, MCPToolObservation)
        assert observation.tool_name == "test_tool"
        assert observation.is_error is False

    def test_call_tool_error(self):
        """Test tool execution with error."""
        # Mock error MCP call
        mock_result = MagicMock(spec=mcp.types.CallToolResult)
        mock_result.content = [
            mcp.types.TextContent(type="text", text="Error occurred")
        ]
        mock_result.isError = True

        # Mock action
        mock_action = MagicMock()
        mock_action.model_dump.return_value = {"param": "value"}

        # Mock call_async_from_sync to return the expected observation
        def mock_call_async_from_sync(coro_func, **kwargs):
            return MCPToolObservation.from_call_tool_result(
                tool_name="test_tool", result=mock_result
            )

        self.mock_client.call_async_from_sync = mock_call_async_from_sync

        observation = self.executor(mock_action)

        assert isinstance(observation, MCPToolObservation)
        assert observation.tool_name == "test_tool"
        assert observation.is_error is True

    def test_call_tool_exception(self):
        """Test tool execution with exception."""
        # Mock action
        mock_action = MagicMock()
        mock_action.model_dump.return_value = {"param": "value"}

        # Mock call_async_from_sync to return an error observation
        def mock_call_async_from_sync(coro_func, **kwargs):
            return MCPToolObservation(
                content=[
                    TextContent(
                        text="Error calling MCP tool test_tool: Connection failed"
                    )
                ],
                is_error=True,
                tool_name="test_tool",
            )

        self.mock_client.call_async_from_sync = mock_call_async_from_sync

        observation = self.executor(mock_action)

        assert isinstance(observation, MCPToolObservation)
        assert isinstance(observation.content[0], TextContent)
        assert observation.tool_name == "test_tool"
        assert observation.is_error is True
        assert "Connection failed" in observation.content[0].text


class TestMCPTool:
    """Test MCPTool functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = MockMCPClient()

        # Create mock MCP tool
        self.mock_mcp_tool = MagicMock(spec=mcp.types.Tool)
        self.mock_mcp_tool.name = "test_tool"
        self.mock_mcp_tool.description = "A test tool"
        self.mock_mcp_tool.inputSchema = {
            "type": "object",
            "properties": {"param": {"type": "string"}},
        }
        self.mock_mcp_tool.annotations = None
        self.mock_mcp_tool.meta = None

        self.tool = MCPTool.from_mcp(
            mcp_tool=self.mock_mcp_tool, mcp_client=self.mock_client
        )

    def test_mcp_tool_creation(self):
        """Test creating an MCP tool."""
        assert self.tool.name == "test_tool"
        assert self.tool.description == "A test tool"

        assert len(self.tool.input_schema["properties"]) == 2
        assert "security_risk" in self.tool.input_schema["properties"]

        # Create a copy to avoid modifying the frozen object
        expected_schema = self.tool.input_schema.copy()
        expected_schema["properties"] = expected_schema["properties"].copy()
        expected_schema["properties"].pop("security_risk")

        assert expected_schema == {
            "type": "object",
            "properties": {"param": {"type": "string"}},
        }

    def test_mcp_tool_with_annotations(self):
        """Test creating an MCP tool with annotations."""
        # Mock tool with annotations
        mock_tool_with_annotations = MagicMock(spec=mcp.types.Tool)
        mock_tool_with_annotations.name = "annotated_tool"
        mock_tool_with_annotations.description = "Tool with annotations"
        mock_tool_with_annotations.inputSchema = {"type": "object"}
        mock_tool_with_annotations.annotations = ToolAnnotations(title="Annotated Tool")
        mock_tool_with_annotations.meta = {"version": "1.0"}

        tool = MCPTool.from_mcp(
            mcp_tool=mock_tool_with_annotations, mcp_client=self.mock_client
        )

        assert tool.name == "annotated_tool"
        assert tool.description == "Tool with annotations"
        assert tool.annotations is not None

    def test_mcp_tool_no_description(self):
        """Test creating an MCP tool without description."""
        # Mock tool without description
        mock_tool_no_desc = MagicMock(spec=mcp.types.Tool)
        mock_tool_no_desc.name = "no_desc_tool"
        mock_tool_no_desc.description = None
        mock_tool_no_desc.inputSchema = {"type": "object"}
        mock_tool_no_desc.annotations = None
        mock_tool_no_desc.meta = None

        tool = MCPTool.from_mcp(mcp_tool=mock_tool_no_desc, mcp_client=self.mock_client)

        assert tool.name == "no_desc_tool"
        assert tool.description == "No description provided"

    def test_executor_assignment(self):
        """Test that the tool has the correct executor."""
        assert isinstance(self.tool.executor, MCPToolExecutor)
        assert self.tool.executor.tool_name == "test_tool"
        assert self.tool.executor.client == self.mock_client


class TestMCPToolImmutability:
    """Test suite for MCPTool immutability features."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_client = MockMCPClient()

        # Create a mock MCP tool
        self.mock_mcp_tool = MagicMock(spec=mcp.types.Tool)
        self.mock_mcp_tool.name = "test_tool"
        self.mock_mcp_tool.description = "Test tool description"
        self.mock_mcp_tool.inputSchema = {
            "type": "object",
            "properties": {"command": {"type": "string"}},
        }
        self.mock_mcp_tool.annotations = None
        self.mock_mcp_tool.meta = {"version": "1.0"}

        self.tool = MCPTool.from_mcp(
            mcp_tool=self.mock_mcp_tool, mcp_client=self.mock_client
        )

    def test_mcp_tool_is_frozen(self):
        """Test that MCPTool instances are frozen and cannot be modified."""
        import pytest

        # Test that direct field assignment raises ValidationError
        with pytest.raises(
            Exception
        ):  # Pydantic raises ValidationError for frozen models
            self.tool.name = "modified_name"

        with pytest.raises(Exception):
            self.tool.description = "modified_description"

        with pytest.raises(Exception):
            self.tool.mcp_client = MockMCPClient()

    def test_mcp_tool_set_executor_returns_new_instance(self):
        """Test that set_executor returns a new MCPTool instance."""
        new_executor = MCPToolExecutor(tool_name="new_tool", client=self.mock_client)
        new_tool = self.tool.set_executor(new_executor)

        # Verify that a new instance was created
        assert new_tool is not self.tool
        assert cast(MCPToolExecutor, self.tool.executor).tool_name == "test_tool"
        assert cast(MCPToolExecutor, new_tool.executor).tool_name == "new_tool"
        assert new_tool.name == self.tool.name
        assert new_tool.description == self.tool.description

    def test_mcp_tool_model_copy_creates_modified_instance(self):
        """Test that model_copy can create modified versions of MCPTool instances."""
        # Create a copy with modified fields
        modified_tool = self.tool.model_copy(
            update={"name": "modified_tool", "description": "Modified description"}
        )

        # Verify that a new instance was created with modifications
        assert modified_tool is not self.tool
        assert self.tool.name == "test_tool"
        assert self.tool.description == "Test tool description"
        assert modified_tool.name == "modified_tool"
        assert modified_tool.description == "Modified description"

    def test_mcp_tool_meta_field_immutability(self):
        """Test that the meta field works correctly and is immutable."""
        # Verify meta field is accessible
        assert self.tool.meta == {"version": "1.0"}

        # Test that meta field cannot be directly modified
        with pytest.raises(Exception):
            self.tool.meta = {"version": "2.0"}

        # Test that meta field can be modified via model_copy
        new_meta = {"version": "2.0", "author": "new_author"}
        modified_tool = self.tool.model_copy(update={"meta": new_meta})
        assert modified_tool.meta == new_meta
        assert self.tool.meta == {"version": "1.0"}  # Original unchanged

    def test_mcp_tool_extra_fields_immutability(self):
        """Test that MCPTool extra fields (mcp_client, mcp_tool) are immutable."""
        # Test that extra fields cannot be directly modified
        with pytest.raises(Exception):
            self.tool.mcp_client = MockMCPClient()

        with pytest.raises(Exception):
            self.tool.mcp_tool = self.mock_mcp_tool

        # Test that extra fields can be accessed
        assert self.tool.mcp_client is self.mock_client
        assert self.tool.mcp_tool is self.mock_mcp_tool

    def test_mcp_tool_from_mcp_creates_immutable_instance(self):
        """Test that MCPTool.from_mcp() creates immutable instances."""
        # Create another tool using from_mcp
        mock_tool2 = MagicMock(spec=mcp.types.Tool)
        mock_tool2.name = "another_tool"
        mock_tool2.description = "Another test tool"
        mock_tool2.inputSchema = {"type": "object"}
        mock_tool2.annotations = None
        mock_tool2.meta = None

        tool2 = MCPTool.from_mcp(mcp_tool=mock_tool2, mcp_client=self.mock_client)

        # Verify it's immutable
        with pytest.raises(Exception):
            tool2.name = "modified_name"

        # Verify it has the correct properties
        assert tool2.name == "another_tool"
        assert tool2.description == "Another test tool"
        assert isinstance(tool2.executor, MCPToolExecutor)

        tool2 = MCPTool.from_mcp(mcp_tool=mock_tool2, mcp_client=self.mock_client)

        # Verify it's immutable
        with pytest.raises(Exception):
            tool2.name = "modified_name"

        # Verify it has the correct properties
        assert tool2.name == "another_tool"
        assert tool2.description == "Another test tool"
        assert isinstance(tool2.executor, MCPToolExecutor)
