"""Test MCP tool JSON serialization with DiscriminatedUnionMixin.

Note: MCPTool serialization may be limited due to complex MCP objects
(mcp_tool field contains mcp.types.Tool which may not be fully JSON serializable).
These tests demonstrate the expected behavior and limitations.
"""

from unittest.mock import Mock

import mcp.types

from openhands.sdk.mcp.client import MCPClient
from openhands.sdk.mcp.tool import MCPTool
from openhands.sdk.tool import Tool


def create_mock_mcp_tool(name: str = "test_tool") -> mcp.types.Tool:
    """Create a mock MCP tool for testing."""
    return mcp.types.Tool(
        name=name,
        description=f"A test MCP tool named {name}",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query parameter"}
            },
            "required": ["query"],
        },
    )


def test_mcp_tool_json_serialization_deserialization() -> None:
    # Create mock MCP tool and client
    mock_mcp_tool = create_mock_mcp_tool()
    mock_client = Mock(spec=MCPClient)
    mcp_tool = MCPTool.create(mock_mcp_tool, mock_client)

    tool_json = mcp_tool.model_dump_json()
    deserialized_tool = MCPTool.model_validate_json(tool_json)
    assert isinstance(deserialized_tool, MCPTool)
    # We use model_dump because tool executor is not serializable and is excluded
    assert deserialized_tool.model_dump() == mcp_tool.model_dump()


def test_mcp_tool_polymorphic_behavior() -> None:
    """Test MCPTool polymorphic behavior using Tool base class."""
    # Create mock MCP tool and client
    mock_mcp_tool = create_mock_mcp_tool()
    mock_client = Mock(spec=MCPClient)

    # Create MCPTool instance
    mcp_tool = MCPTool.create(mock_mcp_tool, mock_client)

    # Should be instance of Tool
    assert isinstance(mcp_tool, Tool)
    assert isinstance(mcp_tool, MCPTool)

    # Check basic properties
    assert mcp_tool.name == "test_tool"
    assert "test MCP tool" in mcp_tool.description
    assert hasattr(mcp_tool, "mcp_tool")


def test_mcp_tool_kind_field() -> None:
    """Test that MCPTool kind field is correctly set."""
    # Create mock MCP tool and client
    mock_mcp_tool = create_mock_mcp_tool()
    mock_client = Mock(spec=MCPClient)

    # Create MCPTool instance
    mcp_tool = MCPTool.create(mock_mcp_tool, mock_client)

    # Check kind field
    assert hasattr(mcp_tool, "kind")
    expected_kind = f"{mcp_tool.__class__.__module__}.{mcp_tool.__class__.__name__}"
    assert mcp_tool.kind == expected_kind


def test_mcp_tool_fallback_behavior() -> None:
    """Test MCPTool fallback behavior with manual data."""
    # Create data that could represent an MCPTool with new schema format
    tool_data = {
        "name": "fallback-tool",
        "description": "A fallback test tool",
        "input_schema": {"name": "fallback-tool-input", "fields": []},
        "output_schema": {"name": "fallback-tool-output", "fields": []},
        "kind": "openhands.sdk.mcp.tool.MCPTool",
        "mcp_tool": {
            "name": "fallback-tool",
            "description": "A fallback test tool",
            "inputSchema": {"type": "object", "properties": {}},
        },
    }

    deserialized_tool = Tool.model_validate(tool_data)
    assert isinstance(deserialized_tool, Tool)
    assert deserialized_tool.name == "fallback-tool"
    assert deserialized_tool.input_schema.name == "fallback-tool-input"
    assert deserialized_tool.output_schema.name == "fallback-tool-output"


def test_mcp_tool_essential_properties() -> None:
    """Test that MCPTool maintains essential properties after creation."""
    # Create mock MCP tool with specific properties
    mock_mcp_tool = mcp.types.Tool(
        name="essential_tool",
        description="Tool with essential properties",
        inputSchema={
            "type": "object",
            "properties": {"param1": {"type": "string"}, "param2": {"type": "integer"}},
            "required": ["param1"],
        },
    )
    mock_client = Mock(spec=MCPClient)

    # Create MCPTool instance
    mcp_tool = MCPTool.create(mock_mcp_tool, mock_client)

    # Verify essential properties are preserved
    assert mcp_tool.name == "essential_tool"
    assert mcp_tool.description == "Tool with essential properties"
    assert mcp_tool.mcp_tool.name == "essential_tool"
    assert mcp_tool.mcp_tool.inputSchema is not None

    # Verify input schema was created correctly
    assert mcp_tool.input_schema is not None
    assert mcp_tool.input_schema.name == "openhands.sdk.mcp.essential_tool.input"
    assert len(mcp_tool.input_schema.fields) == 2

    # Check that the fields were converted correctly
    field_names = {field.name for field in mcp_tool.input_schema.fields}
    assert "param1" in field_names
    assert "param2" in field_names
