"""MCPTool definition and implementation."""

import json
from typing import Any

from pydantic import Field

from openhands.sdk.logger import get_logger
from openhands.sdk.mcp.client import MCPClient
from openhands.sdk.tool import (
    ActionBase,
    ObservationBase,
    Tool,
    ToolAnnotations,
    ToolExecutor,
)


logger = get_logger(__name__)


class MCPToolAction(ActionBase):
    """Action for calling MCP tools."""

    tool_name: str = Field(description="Name of the MCP tool to call")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Arguments to pass to the MCP tool"
    )


class MCPToolObservation(ObservationBase):
    """Observation from MCP tool execution."""

    content: str = Field(default="", description="Content returned from the MCP tool")
    is_error: bool = Field(
        default=False, description="Whether the call resulted in an error"
    )
    error_message: str | None = Field(
        default=None, description="Error message if the call failed"
    )
    tool_name: str = Field(description="Name of the tool that was called")

    @property
    def agent_observation(self) -> str:
        """Format the observation for agent display."""
        if self.is_error:
            return f"Error calling tool {self.tool_name}: {self.error_message}"
        else:
            return (
                f"Tool {self.tool_name} returned: {json.dumps(self.content, indent=2)}"
            )


class MCPToolExecutor(ToolExecutor):
    """Executor for MCP tools."""

    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client

    def __call__(self, action: MCPToolAction) -> MCPToolObservation:
        """Execute an MCP tool call."""
        try:
            result = self.mcp_client.call_tool(action.tool_name, action.arguments)

            return MCPToolObservation(
                content=json.dumps(result.model_dump(mode="json")),
                is_error=result.isError,
                tool_name=action.tool_name,
            )

        except Exception as e:
            error_msg = f"Error calling MCP tool {action.tool_name}: {str(e)}"
            logger.error(error_msg)

            return MCPToolObservation(
                is_error=True,
                error_message=error_msg,
                tool_name=action.tool_name,
            )


class MCPTool(Tool[MCPToolAction, MCPToolObservation]):
    """MCP Tool that wraps an MCP client and provides tool functionality."""

    def __init__(self, mcp_client: MCPClient, tool_name: str):
        """Initialize MCPTool with an MCP client and specific tool name.

        Args:
            mcp_client: The MCP client to use for tool calls
            tool_name: Name of the specific MCP tool to wrap
        """
        if tool_name not in mcp_client.tool_map:
            raise ValueError(f"Tool {tool_name} not found in MCP client")

        mcp_tool = mcp_client.tool_map[tool_name]

        # Create executor
        executor = MCPToolExecutor(mcp_client)

        # Initialize the parent Tool
        super().__init__(
            name=tool_name,
            description=mcp_tool.description or "No description provided",
            input_schema=MCPToolAction,
            output_schema=MCPToolObservation,
            annotations=ToolAnnotations(
                title=tool_name,
                readOnlyHint=False,  # MCP tools can be read-only or not
                destructiveHint=True,  # Conservative default
                idempotentHint=False,  # Conservative default
                openWorldHint=True,  # MCP tools often interact with external systems
            ),
            executor=executor,
        )

        self.mcp_client = mcp_client
        self.mcp_tool = mcp_tool

    def to_mcp_tool(self) -> dict[str, Any]:
        """Convert to MCP tool format using the original MCP tool schema."""
        return {
            "name": self.mcp_tool.name,
            "description": self.mcp_tool.description,
            "inputSchema": self.mcp_tool.inputSchema,
        }


class MCPToolRegistry:
    """Registry for managing MCP tools from multiple clients."""

    def __init__(self):
        self.clients: dict[str, MCPClient] = {}
        self.tools: dict[str, MCPTool] = {}

    def add_client(self, name: str, client: MCPClient) -> None:
        """Add an MCP client to the registry."""
        self.clients[name] = client

        # Create tools for all available tools in the client
        for tool_name in client.tool_map:
            # Use client_name:tool_name as the key to avoid conflicts
            full_tool_name = f"{name}:{tool_name}"
            self.tools[full_tool_name] = MCPTool(client, tool_name)

    def get_tool(self, tool_name: str) -> MCPTool | None:
        """Get a tool by name."""
        return self.tools.get(tool_name)

    def get_all_tools(self) -> list[MCPTool]:
        """Get all registered MCP tools."""
        return list(self.tools.values())

    def get_tools_for_client(self, client_name: str) -> list[MCPTool]:
        """Get all tools for a specific client."""
        return [
            tool
            for name, tool in self.tools.items()
            if name.startswith(f"{client_name}:")
        ]
