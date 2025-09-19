"""Utility functions for MCP integration."""

import logging

import mcp.types
from fastmcp.client.logging import LogMessage
from fastmcp.mcp_config import MCPConfig

from openhands.sdk.logger import get_logger
from openhands.sdk.mcp import MCPClient, MCPTool
from openhands.sdk.tool import ToolType


logger = get_logger(__name__)
LOGGING_LEVEL_MAP = logging.getLevelNamesMapping()


async def log_handler(message: LogMessage):
    """
    Handles incoming logs from the MCP server and forwards them
    to the standard Python logging system.
    """
    msg = message.data.get("msg")
    extra = message.data.get("extra")

    # Convert the MCP log level to a Python log level
    level = LOGGING_LEVEL_MAP.get(message.level.upper(), logging.INFO)

    # Log the message using the standard logging library
    logger.log(level, msg, extra=extra)


async def _list_tools(client: MCPClient) -> list[ToolType]:
    """List tools from an MCP client."""
    tools: list[ToolType] = []

    logger.info("Attempting to connect to MCP server and list tools...")
    try:
        async with client:
            if not client.is_connected():
                logger.error(
                    "Failed to connect to MCP client - client.is_connected() "
                    "returned False"
                )
                raise ConnectionError("MCP client failed to connect")

            logger.info("MCP client connected successfully, listing tools...")
            mcp_type_tools: list[mcp.types.Tool] = await client.list_tools()
            logger.info(f"MCP server returned {len(mcp_type_tools)} tools")

            for tool in mcp_type_tools:
                logger.debug(f"Processing MCP tool: {tool.name} - {tool.description}")

            tools = [
                MCPTool.create(mcp_tool=t, mcp_client=client) for t in mcp_type_tools
            ]
            logger.info(f"Successfully created {len(tools)} MCP tool wrappers")
    except Exception as e:
        logger.error(
            f"Error connecting to MCP server or listing tools: "
            f"{type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        raise

    if client.is_connected():
        logger.warning(
            "MCP client still connected after context exit - this is unexpected"
        )

    return tools


def create_mcp_tools(
    config: dict | MCPConfig,
    timeout: float = 30.0,
) -> list[ToolType]:
    """Create MCP tools from MCP configuration."""
    tools: list[ToolType] = []

    logger.info(f"Starting MCP tool creation with config: {config}")
    logger.info(f"MCP connection timeout set to {timeout} seconds")

    try:
        if isinstance(config, dict):
            logger.debug("Converting dict config to MCPConfig")
            config = MCPConfig.model_validate(config)

        logger.info(f"Creating MCP client with config: {config}")
        client = MCPClient(config, log_handler=log_handler)

        logger.info(f"Calling _list_tools with timeout={timeout}s")
        tools = client.call_async_from_sync(_list_tools, timeout=timeout, client=client)

        logger.info(
            f"Successfully created {len(tools)} MCP tools: {[t.name for t in tools]}"
        )
    except TimeoutError as e:
        logger.error(
            f"Timeout after {timeout}s while connecting to MCP server: {str(e)}"
        )
        raise
    except Exception as e:
        logger.error(
            f"Failed to create MCP tools: {type(e).__name__}: {str(e)}", exc_info=True
        )
        raise

    return tools
