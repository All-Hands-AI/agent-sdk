"""Utility functions for MCP integration."""

import traceback
from typing import TYPE_CHECKING

import mcp.types

from openhands.sdk.llm import TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.mcp import MCPToolObservation
from openhands.sdk.tool import MCPActionBase, Tool, ToolAnnotations, ToolExecutor


if TYPE_CHECKING:
    from openhands.sdk.mcp.client import MCPClient

logger = get_logger(__name__)


# NOTE: We don't define MCPToolAction because it
# will be a pydantic BaseModel dynamically created from the MCP tool schema.
# It will be available as "tool.action_type".


class MCPToolExecutor(ToolExecutor):
    """Executor for MCP tools."""

    def __init__(self, tool_name: str, client: "MCPClient"):
        self.tool_name = tool_name
        self.client = client

    async def call_tool(self, action: MCPActionBase) -> MCPToolObservation:
        async with self.client:
            assert self.client.is_connected(), "MCP client is not connected."
            try:
                logger.debug(
                    f"Calling MCP tool {self.tool_name} "
                    f"with args: {action.model_dump()}"
                )
                result: mcp.types.CallToolResult = await self.client.call_tool_mcp(
                    name=self.tool_name, arguments=action.model_dump(exclude_none=True)
                )
                return MCPToolObservation.from_call_tool_result(
                    tool_name=self.tool_name, result=result
                )
            except Exception as e:
                traceback_str = traceback.format_exc()
                error_msg = (
                    f"Error calling MCP tool {self.tool_name}"
                    f": {str(e)}\n{traceback_str}"
                )
                logger.error(error_msg)
                return MCPToolObservation(
                    content=[TextContent(text=error_msg)],
                    is_error=True,
                    tool_name=self.tool_name,
                )

    def __call__(self, action: MCPActionBase) -> MCPToolObservation:
        """Execute an MCP tool call."""
        return self.client.call_async_from_sync(
            self.call_tool, action=action, timeout=60.0
        )


class MCPTool(Tool[MCPActionBase, MCPToolObservation]):
    """MCP Tool that wraps an MCP client and provides tool functionality."""

    def __init__(
        self,
        mcp_tool: mcp.types.Tool,
        mcp_client: "MCPClient",
    ):
        self.mcp_client = mcp_client
        self.mcp_tool = mcp_tool
        super().__init__(
            name=mcp_tool.name,
            description=mcp_tool.description or "No description provided",
            input_schema=mcp_tool.inputSchema,
            output_schema=MCPToolObservation,
            annotations=ToolAnnotations.model_validate(mcp_tool.annotations)
            if mcp_tool.annotations
            else None,
            _meta=mcp_tool.meta,
            executor=MCPToolExecutor(tool_name=mcp_tool.name, client=mcp_client),
        )
