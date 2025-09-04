"""MCP (Model Context Protocol) integration for agent-sdk."""

from openhands.sdk.mcp.client import MCPClient
from openhands.sdk.mcp.tool import (
    MCPTool,
    MCPToolAction,
    MCPToolExecutor,
    MCPToolObservation,
    MCPToolRegistry,
)
from openhands.sdk.mcp.utils import (
    create_mcp_client,
    create_mcp_tools_from_config,
)


__all__ = [
    # Client
    "MCPClient",
    # Tools
    "MCPTool",
    "MCPToolAction",
    "MCPToolObservation",
    "MCPToolExecutor",
    "MCPToolRegistry",
    # Utilities
    "create_mcp_client",
    "create_mcp_tools_from_config",
]
