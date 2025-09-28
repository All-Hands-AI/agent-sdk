import mcp.types
import pytest
from unittest.mock import Mock

from openhands.sdk.mcp.tool import MCPTool
from openhands.sdk.mcp.client import MCPClient


def _make_tool_with_schema(schema: dict):
    mcp_tool = mcp.types.Tool(
        name="fetch",
        description="Fetch a URL",
        inputSchema=schema,
    )
    client = Mock(spec=MCPClient)
    return MCPTool.create(mcp_tool, client)[0]


def test_mcp_action_from_arguments_validates_and_sanitizes():
    tool = _make_tool_with_schema(
        {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "timeout": {"type": "number"},
            },
            "required": ["url"],
        }
    )

    # includes an extra field that should be rejected and a None that should be dropped
    args = {"url": "https://example.com", "timeout": None}
    action = tool.action_from_arguments(args)
    assert action.data == {"url": "https://example.com"}


def test_mcp_action_from_arguments_raises_on_invalid():
    tool = _make_tool_with_schema(
        {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
            },
            "required": ["url"],
        }
    )

    # missing required url
    with pytest.raises(Exception):
        tool.action_from_arguments({})

    # extra field should also cause validation error
    with pytest.raises(Exception):
        tool.action_from_arguments({"url": "https://x.com", "data": {"x": 1}})
