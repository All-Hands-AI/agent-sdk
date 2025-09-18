"""Utility functions for MCP integration."""

import re

import mcp.types
from pydantic import Field, ValidationError

from openhands.sdk.llm import TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.mcp.client import MCPClient
from openhands.sdk.mcp.definition import MCPToolAction, MCPToolObservation
from openhands.sdk.tool import Tool, ToolAnnotations, ToolExecutor


logger = get_logger(__name__)


# NOTE: We don't define MCPToolAction because it
# will be a pydantic BaseModel dynamically created from the MCP tool schema.
# It will be available as "tool.action_type".


def to_camel_case(s: str) -> str:
    parts = re.split(r"[_\-\s]+", s)
    return "".join(word.capitalize() for word in parts if word)


class MCPToolExecutor(ToolExecutor):
    """Executor for MCP tools."""

    def __init__(self, tool_name: str, client: MCPClient):
        self.tool_name = tool_name
        self.client = client

    async def call_tool(self, action: MCPToolAction) -> MCPToolObservation:
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

    def __call__(self, action: MCPToolAction) -> MCPToolObservation:
        """Execute an MCP tool call."""
        return self.client.call_async_from_sync(
            self.call_tool, action=action, timeout=300
        )


class MCPTool(Tool[MCPToolAction, MCPToolObservation]):
    """MCP Tool that wraps an MCP client and provides tool functionality."""

    mcp_tool: mcp.types.Tool = Field(description="The MCP tool definition.")

    @classmethod
    def create(
        cls,
        mcp_tool: mcp.types.Tool,
        mcp_client: MCPClient,
    ) -> "MCPTool":
        try:
            annotations = (
                ToolAnnotations.model_validate(
                    mcp_tool.annotations.model_dump(exclude_none=True)
                )
                if mcp_tool.annotations
                else None
            )

            return cls(
                name=mcp_tool.name,
                description=mcp_tool.description or "No description provided",
                action_type=MCPToolAction,
                observation_type=MCPToolObservation,
                annotations=annotations,
                meta=mcp_tool.meta,
                executor=MCPToolExecutor(tool_name=mcp_tool.name, client=mcp_client),
                # pass-through fields (enabled by **extra in Tool.create)
                mcp_tool=mcp_tool,
            )
        except ValidationError as e:
            logger.error(
                f"Validation error creating MCPTool for {mcp_tool.name}: "
                f"{e.json(indent=2)}",
                exc_info=True,
            )
            raise e
