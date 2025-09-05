"""Utility functions for MCP integration."""

from openhands.sdk.config.mcp_config import (
    MCPConfig,
    MCPSHTTPServerConfig,
    MCPSSEServerConfig,
    MCPStdioServerConfig,
)
from openhands.sdk.logger import get_logger
from openhands.sdk.mcp.client import MCPClient
from openhands.sdk.mcp.tool import MCPToolRegistry
from openhands.sdk.tool import Tool


logger = get_logger(__name__)


def create_mcp_client(
    server_config: MCPSSEServerConfig | MCPSHTTPServerConfig | MCPStdioServerConfig,
    conversation_id: str | None = None,
    timeout: float = 30.0,
) -> MCPClient:
    """Create and connect an MCP client from server configuration.

    Args:
        server_config: MCP server configuration
        conversation_id: Optional conversation ID for HTTP-based servers
        timeout: Connection timeout in seconds

    Returns:
        Connected MCP client

    Raises:
        Exception: If connection fails
    """
    client = MCPClient()

    if isinstance(server_config, (MCPSSEServerConfig, MCPSHTTPServerConfig)):
        client.connect_http(server_config, conversation_id, timeout)
    elif isinstance(server_config, MCPStdioServerConfig):
        client.connect_stdio(server_config, timeout)
    else:
        raise ValueError(f"Unsupported server config type: {type(server_config)}")

    return client


def create_mcp_tools_from_config(
    mcp_config: MCPConfig,
    conversation_id: str | None = None,
    timeout: float = 30.0,
) -> list[Tool]:
    """Create MCP tools from MCP configuration.

    Args:
        mcp_config: MCP configuration containing server definitions
        conversation_id: Optional conversation ID for HTTP-based servers
        timeout: Connection timeout in seconds

    Returns:
        List of MCP tools ready to use with agents

    Raises:
        Exception: If any server connection fails
    """
    tools: list[Tool] = []
    registry = MCPToolRegistry()

    # Process SSE servers
    for server_config in mcp_config.sse_servers:
        try:
            client = create_mcp_client(server_config, conversation_id, timeout)
            server_name = getattr(server_config, "name", server_config.url)
            registry.add_client(server_name, client)
            logger.info(f"Connected to SSE server: {server_name}")
        except Exception as e:
            logger.error(f"Failed to connect to SSE server {server_config.url}: {e}")
            # Continue with other servers instead of failing completely

    # Process SHTTP servers
    for server_config in mcp_config.shttp_servers:
        try:
            client = create_mcp_client(server_config, conversation_id, timeout)
            server_name = getattr(server_config, "name", server_config.url)
            registry.add_client(server_name, client)
            logger.info(f"Connected to SHTTP server: {server_name}")
        except Exception as e:
            logger.error(f"Failed to connect to SHTTP server {server_config.url}: {e}")
            # Continue with other servers instead of failing completely

    # Process stdio servers
    for server_config in mcp_config.stdio_servers:
        try:
            client = create_mcp_client(server_config, conversation_id, timeout)
            server_name = getattr(server_config, "name", server_config.command)
            registry.add_client(server_name, client)
            logger.info(f"Connected to stdio server: {server_name}")
        except Exception as e:
            logger.error(
                f"Failed to connect to stdio server {server_config.command}: {e}"
            )
            # Continue with other servers instead of failing completely

    # Convert all MCP tools to agent-sdk tools
    tools.extend(registry.get_all_tools())

    logger.info(f"Created {len(tools)} MCP tools from {len(registry.clients)} servers")
    return tools
