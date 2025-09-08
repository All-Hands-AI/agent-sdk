"""Utility functions for MCP integration."""

import re
from typing import TYPE_CHECKING

import mcp.types
from pydantic import ValidationError

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


def to_camel_case(s: str) -> str:
    parts = re.split(r"[_\-\s]+", s)
    return "".join(word.capitalize() for word in parts if word)


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
                    name=self.tool_name, arguments=action.to_mcp_arguments()
                )
                return MCPToolObservation.from_call_tool_result(
                    tool_name=self.tool_name, result=result
                )
            except Exception as e:
                error_msg = f"Error calling MCP tool {self.tool_name}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return MCPToolObservation(
                    content=[TextContent(text=error_msg)],
                    is_error=True,
                    tool_name=self.tool_name,
                )

    def __call__(self, action: MCPActionBase) -> MCPToolObservation:
        """Execute an MCP tool call."""
        return self.client.call_async_from_sync(
            self.call_tool, action=action, timeout=300
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

        try:
            if mcp_tool.annotations:
                anno_dict = mcp_tool.annotations.model_dump(exclude_none=True)
                annotations = ToolAnnotations.model_validate(anno_dict)
            else:
                annotations = None

            MCPActionType = MCPActionBase.from_mcp_schema(
                f"{to_camel_case(mcp_tool.name)}Action", mcp_tool.inputSchema
            )
            super().__init__(
                name=mcp_tool.name,
                description=mcp_tool.description or "No description provided",
                input_schema=MCPActionType,
                output_schema=MCPToolObservation,
                annotations=annotations,
                _meta=mcp_tool.meta,
                executor=MCPToolExecutor(tool_name=mcp_tool.name, client=mcp_client),
            )
        except ValidationError as e:
            logger.error(
                f"Validation error creating MCPTool for {mcp_tool.name}: "
                f"{e.json(indent=2)}",
                exc_info=True,
            )
            raise e
