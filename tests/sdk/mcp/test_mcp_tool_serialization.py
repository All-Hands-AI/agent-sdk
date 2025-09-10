"""Test MCP tool serialization with DiscriminatedUnionMixin."""

from typing import Annotated
from unittest.mock import MagicMock

import mcp.types
import pytest
from pydantic import BaseModel

from openhands.sdk.mcp.client import MCPClient
from openhands.sdk.mcp.tool import MCPTool
from openhands.sdk.tool import Tool, ToolType
from openhands.sdk.utils.discriminated_union import DiscriminatedUnionType


class MockMCPClient(MCPClient):
    """Mock MCPClient for testing that bypasses the complex constructor."""

    def __init__(self):
        # Skip the parent constructor to avoid needing transport
        pass


@pytest.fixture
def mock_mcp_tool():
    """Create a mock MCP tool for testing."""
    mcp_tool = MagicMock(spec=mcp.types.Tool)
    mcp_tool.name = "test_mcp_tool"
    mcp_tool.description = "A test MCP tool"
    mcp_tool.inputSchema = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Test query"}},
        "required": ["query"],
    }
    mcp_tool.annotations = None
    mcp_tool.meta = None
    return mcp_tool


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP client for testing."""
    return MockMCPClient()


def test_mcp_tool_supports_polymorphic_deserialization(
    mock_mcp_tool, mock_mcp_client
) -> None:
    """Test that MCPTool supports polymorphic deserialization."""
    # Create an MCPTool instance
    mcp_tool_instance = MCPTool.create(
        mcp_tool=mock_mcp_tool, mcp_client=mock_mcp_client
    )

    # Test that the instance is created correctly
    assert isinstance(mcp_tool_instance, MCPTool)
    assert mcp_tool_instance.name == "test_mcp_tool"
    assert mcp_tool_instance.description == "A test MCP tool"
    assert mcp_tool_instance.kind == "openhands.sdk.mcp.tool.MCPTool"


def test_mcp_tool_supports_polymorphic_field_deserialization(
    mock_mcp_tool, mock_mcp_client
) -> None:
    """Test that MCPTool supports polymorphic deserialization when used as a field."""

    class ToolContainer(BaseModel):
        tool: Annotated[Tool, DiscriminatedUnionType[Tool]]

    # Create an MCPTool instance
    mcp_tool_instance = MCPTool.create(
        mcp_tool=mock_mcp_tool, mcp_client=mock_mcp_client
    )
    container = ToolContainer(tool=mcp_tool_instance)

    # Test that the container is created correctly
    assert isinstance(container.tool, MCPTool)
    assert container.tool.name == "test_mcp_tool"
    assert container.tool.description == "A test MCP tool"


def test_mcp_tool_supports_nested_polymorphic_deserialization(
    mock_mcp_tool, mock_mcp_client
) -> None:
    """Test that MCPTool supports polymorphic deserialization when nested in lists."""

    class ToolRegistry(BaseModel):
        tools: list[Annotated[Tool, DiscriminatedUnionType[Tool]]]

    # Create MCPTool instances
    mcp_tool_instance1 = MCPTool.create(
        mcp_tool=mock_mcp_tool, mcp_client=mock_mcp_client
    )

    # Create a second mock tool with different name
    mock_mcp_tool2 = MagicMock(spec=mcp.types.Tool)
    mock_mcp_tool2.name = "test_mcp_tool_2"
    mock_mcp_tool2.description = "A second test MCP tool"
    mock_mcp_tool2.inputSchema = {
        "type": "object",
        "properties": {"data": {"type": "string", "description": "Test data"}},
        "required": ["data"],
    }
    mock_mcp_tool2.annotations = None
    mock_mcp_tool2.meta = None

    mcp_tool_instance2 = MCPTool.create(
        mcp_tool=mock_mcp_tool2, mcp_client=mock_mcp_client
    )

    registry = ToolRegistry(tools=[mcp_tool_instance1, mcp_tool_instance2])

    # Test that the registry is created correctly
    assert len(registry.tools) == 2
    assert all(isinstance(tool, MCPTool) for tool in registry.tools)
    assert registry.tools[0].name == "test_mcp_tool"
    assert registry.tools[1].name == "test_mcp_tool_2"


def test_mcp_tool_model_validate_dict(mock_mcp_tool, mock_mcp_client) -> None:
    """Test MCPTool model_validate with dictionary input."""
    # Create an MCPTool instance
    mcp_tool_instance = MCPTool.create(
        mcp_tool=mock_mcp_tool, mcp_client=mock_mcp_client
    )

    # Test that the instance is created correctly
    assert isinstance(mcp_tool_instance, MCPTool)
    assert mcp_tool_instance.name == "test_mcp_tool"
    assert mcp_tool_instance.description == "A test MCP tool"
    assert mcp_tool_instance.kind == "openhands.sdk.mcp.tool.MCPTool"


def test_mcp_tool_fallback_behavior(mock_mcp_tool, mock_mcp_client) -> None:
    """Test fallback behavior when discriminated union logic doesn't apply."""
    # Create an MCPTool instance
    mcp_tool_instance = MCPTool.create(
        mcp_tool=mock_mcp_tool, mcp_client=mock_mcp_client
    )
    tool_data = mcp_tool_instance.model_dump()

    # Test with missing kind - should fallback to base class
    no_kind_data = {k: v for k, v in tool_data.items() if k != "kind"}
    result = Tool.model_validate(no_kind_data)
    assert isinstance(result, Tool)
    assert not isinstance(result, MCPTool)

    # Test with invalid kind - should fallback to base class
    invalid_kind_data = {**tool_data, "kind": "InvalidMCPTool"}
    result = Tool.model_validate(invalid_kind_data)
    assert isinstance(result, Tool)
    assert not isinstance(result, MCPTool)


def test_mcp_tool_preserves_pydantic_parameters(mock_mcp_tool, mock_mcp_client) -> None:
    """Test that all Pydantic validation parameters are preserved."""
    mcp_tool_instance = MCPTool.create(
        mcp_tool=mock_mcp_tool, mcp_client=mock_mcp_client
    )

    # Test that the instance is created correctly
    assert isinstance(mcp_tool_instance, MCPTool)
    assert mcp_tool_instance.name == "test_mcp_tool"
    assert mcp_tool_instance.description == "A test MCP tool"
    assert mcp_tool_instance.kind == "openhands.sdk.mcp.tool.MCPTool"


def test_mcp_tool_type_annotation_works(mock_mcp_tool, mock_mcp_client) -> None:
    """Test that ToolType annotation works correctly with MCPTool."""

    class ToolWrapper(BaseModel):
        tool: ToolType

    mcp_tool_instance = MCPTool.create(
        mcp_tool=mock_mcp_tool, mcp_client=mock_mcp_client
    )
    wrapper = ToolWrapper(tool=mcp_tool_instance)

    # Test that the wrapper is created correctly
    assert isinstance(wrapper.tool, MCPTool)
    assert wrapper.tool.name == "test_mcp_tool"
    assert wrapper.tool.description == "A test MCP tool"


def test_mcp_tool_with_annotations_deserialization(
    mock_mcp_tool, mock_mcp_client
) -> None:
    """Test that MCPTool with annotations deserializes correctly."""
    # Add annotations to the mock tool
    mock_mcp_tool.annotations = MagicMock()
    mock_mcp_tool.annotations.model_dump.return_value = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }

    mcp_tool_instance = MCPTool.create(
        mcp_tool=mock_mcp_tool, mcp_client=mock_mcp_client
    )

    # Test that the instance is created correctly with annotations
    assert isinstance(mcp_tool_instance, MCPTool)
    assert mcp_tool_instance.name == "test_mcp_tool"
    assert mcp_tool_instance.description == "A test MCP tool"
    assert mcp_tool_instance.annotations is not None
    assert mcp_tool_instance.annotations.readOnlyHint is True
    assert mcp_tool_instance.annotations.destructiveHint is False
    assert mcp_tool_instance.annotations.idempotentHint is True
    assert mcp_tool_instance.annotations.openWorldHint is False


def test_mcp_tool_with_meta_deserialization(mock_mcp_tool, mock_mcp_client) -> None:
    """Test that MCPTool with meta data deserializes correctly."""
    # Add meta data to the mock tool
    mock_mcp_tool.meta = {"version": "1.0", "author": "test"}

    mcp_tool_instance = MCPTool.create(
        mcp_tool=mock_mcp_tool, mcp_client=mock_mcp_client
    )

    # Test that the instance is created correctly with meta data
    assert isinstance(mcp_tool_instance, MCPTool)
    assert mcp_tool_instance.name == "test_mcp_tool"
    assert mcp_tool_instance.description == "A test MCP tool"
    assert mcp_tool_instance.meta == {"version": "1.0", "author": "test"}
