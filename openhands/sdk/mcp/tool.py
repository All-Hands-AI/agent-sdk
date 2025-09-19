"""Utility functions for MCP integration."""

import re

import mcp.types
from pydantic import Field, ValidationError

from openhands.sdk.llm import TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.mcp import MCPToolObservation
from openhands.sdk.mcp.client import MCPClient
from openhands.sdk.tool import MCPActionBase, Tool, ToolAnnotations, ToolExecutor


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

    async def call_tool(self, action: MCPActionBase) -> MCPToolObservation:
        logger.info(f"Starting MCP tool execution for '{self.tool_name}'")
        logger.debug(f"Tool arguments: {action.model_dump()}")

        try:
            async with self.client:
                if not self.client.is_connected():
                    error_msg = (
                        f"MCP client is not connected when trying to call tool "
                        f"'{self.tool_name}'"
                    )
                    logger.error(error_msg)
                    return MCPToolObservation(
                        content=[TextContent(text=error_msg)],
                        is_error=True,
                        tool_name=self.tool_name,
                    )

                logger.info(f"MCP client connected, calling tool '{self.tool_name}'")
                logger.debug(f"MCP arguments being sent: {action.to_mcp_arguments()}")

                result: mcp.types.CallToolResult = await self.client.call_tool_mcp(
                    name=self.tool_name, arguments=action.to_mcp_arguments()
                )

                if result.isError:
                    logger.warning(
                        f"MCP tool '{self.tool_name}' returned an error: {result}"
                    )
                else:
                    logger.info(f"MCP tool '{self.tool_name}' executed successfully")
                    logger.debug(f"Tool result: {result}")

                return MCPToolObservation.from_call_tool_result(
                    tool_name=self.tool_name, result=result
                )
        except TimeoutError as e:
            error_msg = f"Timeout calling MCP tool '{self.tool_name}': {str(e)}"
            logger.error(error_msg)
            return MCPToolObservation(
                content=[TextContent(text=error_msg)],
                is_error=True,
                tool_name=self.tool_name,
            )
        except ConnectionError as e:
            error_msg = (
                f"Connection error calling MCP tool '{self.tool_name}': {str(e)}"
            )
            logger.error(error_msg)
            return MCPToolObservation(
                content=[TextContent(text=error_msg)],
                is_error=True,
                tool_name=self.tool_name,
            )
        except Exception as e:
            error_msg = (
                f"Unexpected error calling MCP tool '{self.tool_name}': "
                f"{type(e).__name__}: {str(e)}"
            )
            logger.error(error_msg, exc_info=True)
            return MCPToolObservation(
                content=[TextContent(text=error_msg)],
                is_error=True,
                tool_name=self.tool_name,
            )

    def __call__(self, action: MCPActionBase) -> MCPToolObservation:
        """Execute an MCP tool call."""
        logger.info(
            f"Synchronously executing MCP tool '{self.tool_name}' with 300s timeout"
        )
        try:
            result = self.client.call_async_from_sync(
                self.call_tool, action=action, timeout=300
            )
            logger.info(f"Sync execution of MCP tool '{self.tool_name}' completed")
            return result
        except Exception as e:
            logger.error(
                f"Sync execution of MCP tool '{self.tool_name}' failed: "
                f"{type(e).__name__}: {str(e)}"
            )
            raise


class MCPTool(Tool[MCPActionBase, MCPToolObservation]):
    """MCP Tool that wraps an MCP client and provides tool functionality."""

    mcp_tool: mcp.types.Tool = Field(description="The MCP tool definition.")

    @classmethod
    def create(
        cls,
        mcp_tool: mcp.types.Tool,
        mcp_client: MCPClient,
    ) -> "MCPTool":
        logger.debug(f"Creating MCPTool wrapper for '{mcp_tool.name}'")
        try:
            annotations = (
                ToolAnnotations.model_validate(
                    mcp_tool.annotations.model_dump(exclude_none=True)
                )
                if mcp_tool.annotations
                else None
            )

            MCPActionType = MCPActionBase.from_mcp_schema(
                f"{to_camel_case(mcp_tool.name)}Action",
                mcp_tool.inputSchema,
            )

            tool = cls(
                name=mcp_tool.name,
                description=mcp_tool.description or "No description provided",
                action_type=MCPActionType,
                observation_type=MCPToolObservation,
                annotations=annotations,
                meta=mcp_tool.meta,
                executor=MCPToolExecutor(tool_name=mcp_tool.name, client=mcp_client),
                # pass-through fields (enabled by **extra in Tool.create)
                mcp_tool=mcp_tool,
            )
            logger.debug(f"Successfully created MCPTool wrapper for '{mcp_tool.name}'")
            return tool
        except ValidationError as e:
            logger.error(
                f"Validation error creating MCPTool for {mcp_tool.name}: "
                f"{e.json(indent=2)}",
                exc_info=True,
            )
            raise e
