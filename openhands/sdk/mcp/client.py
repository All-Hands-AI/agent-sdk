"""MCP Client implementation."""

from typing import Optional

from fastmcp import Client
from fastmcp.client.transports import (
    SSETransport,
    StdioTransport,
    StreamableHttpTransport,
)
from mcp import McpError
from mcp.types import CallToolResult, Tool as MCPTool
from pydantic import BaseModel, ConfigDict, Field

from openhands.sdk.config.mcp_config import (
    MCPSHTTPServerConfig,
    MCPSSEServerConfig,
    MCPStdioServerConfig,
)
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class MCPClient(BaseModel):
    """MCP client that connects to servers and manages available tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: Optional[Client] = None
    tools: list[MCPTool] = Field(default_factory=list)
    tool_map: dict[str, MCPTool] = Field(default_factory=dict)
    server_config: (
        MCPSSEServerConfig | MCPSHTTPServerConfig | MCPStdioServerConfig | None
    ) = None

    # Connection parameters for client recreation
    _timeout: float = 30.0
    _conversation_id: Optional[str] = None

    def _create_stdio_client(self) -> Client:
        """Create a new stdio client using stored server config."""
        if not isinstance(self.server_config, MCPStdioServerConfig):
            raise RuntimeError("Server config is not for stdio transport")

        transport = StdioTransport(
            command=self.server_config.command,
            args=self.server_config.args or [],
            env=self.server_config.env,
        )
        return Client(transport, timeout=self._timeout)

    def _create_http_client(self) -> Client:
        """Create a new HTTP client using stored server config."""
        if not isinstance(
            self.server_config, (MCPSSEServerConfig, MCPSHTTPServerConfig)
        ):
            raise RuntimeError("Server config is not for HTTP transport")

        server_url = self.server_config.url
        api_key = self.server_config.api_key

        if not server_url:
            raise ValueError("Server URL is required.")

        headers = (
            {
                "Authorization": f"Bearer {api_key}",
                "s": api_key,  # For action execution server's MCP Router
                "X-Session-API-Key": api_key,  # For Remote Runtime
            }
            if api_key
            else {}
        )

        if self._conversation_id:
            headers["X-OpenHands-ServerConversation-ID"] = self._conversation_id

        # Instantiate custom transports due to custom headers
        if isinstance(self.server_config, MCPSHTTPServerConfig):
            transport = StreamableHttpTransport(
                url=server_url,
                headers=headers if headers else None,
            )
        else:
            transport = SSETransport(
                url=server_url,
                headers=headers if headers else None,
            )

        return Client(transport, timeout=self._timeout)

    async def _initialize_and_list_tools(self) -> None:
        """Initialize session and populate tool map."""
        if not self.client:
            raise RuntimeError("Session not initialized.")

        async with self.client:
            tools = await self.client.list_tools()

        # Clear existing tools
        self.tools = []
        self.tool_map = {}

        # Store tools directly as MCP Tool objects
        for tool in tools:
            self.tool_map[tool.name] = tool
            self.tools.append(tool)

        logger.info(f"Connected to server with tools: {[tool.name for tool in tools]}")

    async def connect_http(
        self,
        server: MCPSSEServerConfig | MCPSHTTPServerConfig,
        conversation_id: str | None = None,
        timeout: float = 30.0,
    ):
        """Connect to MCP server using SHTTP or SSE transport."""
        server_url = server.url

        if not server_url:
            raise ValueError("Server URL is required.")

        try:
            # Store connection parameters for recreation
            self.server_config = server
            self._timeout = timeout
            self._conversation_id = conversation_id

            # Create initial client for tool listing
            self.client = self._create_http_client()
            await self._initialize_and_list_tools()
        except McpError as e:
            error_msg = f"McpError connecting to {server_url}: {e}"
            logger.error(error_msg)
            raise
        except Exception as e:
            error_msg = f"Error connecting to {server_url}: {e}"
            logger.error(error_msg)
            raise

    async def connect_stdio(self, server: MCPStdioServerConfig, timeout: float = 30.0):
        """Connect to MCP server using stdio transport."""
        try:
            # Store connection parameters for recreation
            self.server_config = server
            self._timeout = timeout

            # Create initial client for tool listing
            self.client = self._create_stdio_client()
            await self._initialize_and_list_tools()
        except Exception as e:
            server_name = getattr(
                server, "name", f"{server.command} {' '.join(server.args or [])}"
            )
            error_msg = f"Failed to connect to stdio server {server_name}: {e}"
            logger.error(error_msg)
            raise

    async def call_tool(self, tool_name: str, args: dict) -> CallToolResult:
        """Call a tool on the MCP server."""
        if tool_name not in self.tool_map:
            raise ValueError(f"Tool {tool_name} not found.")

        if not self.server_config:
            raise RuntimeError("Server config is not available.")

        # Recreate client for each tool call
        if isinstance(self.server_config, MCPStdioServerConfig):
            fresh_client = self._create_stdio_client()
        else:
            fresh_client = self._create_http_client()

        async with fresh_client:
            return await fresh_client.call_tool_mcp(name=tool_name, arguments=args)
