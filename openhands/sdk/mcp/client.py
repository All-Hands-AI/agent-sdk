"""MCP Client implementation."""

import asyncio
import threading
from typing import Optional

from fastmcp import Client
from fastmcp.client.transports import (
    SSETransport,
    StdioTransport,
    StreamableHttpTransport,
)
from mcp import McpError
from mcp.types import CallToolResult, Tool as MCPTool
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from openhands.sdk.config.mcp_config import (
    MCPSHTTPServerConfig,
    MCPSSEServerConfig,
    MCPStdioServerConfig,
)
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class MCPClient(BaseModel):
    """MCP client that connects to servers and manages available tools.

    This client provides a synchronous API while managing async operations internally
    using a dedicated event loop in a background thread.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tools: list[MCPTool] = Field(default_factory=list)
    tool_map: dict[str, MCPTool] = Field(default_factory=dict)
    server_config: Optional[
        MCPSSEServerConfig | MCPSHTTPServerConfig | MCPStdioServerConfig
    ] = Field(default=None)

    # Connection parameters for recreating clients
    _timeout: float = Field(default=30.0, exclude=True)
    _conversation_id: Optional[str] = Field(default=None, exclude=True)

    # Private attributes - these don't get serialized
    _timeout: float = PrivateAttr(default=30.0)
    _conversation_id: Optional[str] = PrivateAttr(default=None)
    _loop: Optional[asyncio.AbstractEventLoop] = PrivateAttr(default=None)
    _thread: Optional[threading.Thread] = PrivateAttr(default=None)
    _loop_lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

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

    def connect_http(
        self,
        server: MCPSSEServerConfig | MCPSHTTPServerConfig,
        conversation_id: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Connect to MCP server using SHTTP or SSE transport."""
        server_url = server.url

        if not server_url:
            raise ValueError("Server URL is required.")

        try:
            # Store connection parameters
            self.server_config = server
            self._timeout = timeout
            self._conversation_id = conversation_id

            # Initialize tools using async method
            self._run_async(self._initialize_and_list_tools_async())
        except McpError as e:
            error_msg = f"McpError connecting to {server_url}: {e}"
            logger.error(error_msg)
            raise
        except Exception as e:
            error_msg = f"Error connecting to {server_url}: {e}"
            logger.error(error_msg)
            raise

    def connect_stdio(
        self, server: MCPStdioServerConfig, timeout: float = 30.0
    ) -> None:
        """Connect to MCP server using stdio transport."""
        try:
            # Store connection parameters
            self.server_config = server
            self._timeout = timeout

            # Initialize tools using async method
            self._run_async(self._initialize_and_list_tools_async())
        except Exception as e:
            server_name = getattr(
                server, "name", f"{server.command} {' '.join(server.args or [])}"
            )
            error_msg = f"Failed to connect to stdio server {server_name}: {e}"
            logger.error(error_msg)
            raise

    def call_tool(self, tool_name: str, args: dict) -> CallToolResult:
        """Call a tool on the MCP server."""
        return self._run_async(self._call_tool_async(tool_name, args))

    async def _initialize_and_list_tools_async(self) -> None:
        """Initialize session and populate tool map (async version)."""
        # Create client for tool listing
        if isinstance(self.server_config, MCPStdioServerConfig):
            client = self._create_stdio_client()
        else:
            client = self._create_http_client()

        async with client:
            tools = await client.list_tools()

        # Clear existing tools
        self.tools = []
        self.tool_map = {}

        # Store tools directly as MCP Tool objects
        for tool in tools:
            self.tool_map[tool.name] = tool
            self.tools.append(tool)

        logger.info(f"Connected to server with tools: {[tool.name for tool in tools]}")

    async def _call_tool_async(self, tool_name: str, args: dict) -> CallToolResult:
        """Call a tool on the MCP server (async version)."""
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

    def _start_event_loop(self) -> None:
        """Start the background event loop for async operations."""
        if self._loop is not None:
            return  # Already started

        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()

        # Wait for loop to be ready
        while self._loop is None:
            threading.Event().wait(0.01)

    def _stop_event_loop(self) -> None:
        """Stop the background event loop."""
        if self._loop is not None and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except RuntimeError:
                # Loop might already be stopped/closed
                pass

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        self._loop = None
        self._thread = None

    def _run_async(self, coro):
        """Run an async coroutine in the managed event loop."""
        with self._loop_lock:
            if self._loop is None:
                self._start_event_loop()
            loop = self._loop

        assert loop is not None
        try:
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result()
        except Exception as e:
            # Add context about which operation failed
            raise RuntimeError(f"MCP async operation failed: {e}") from e

    def __del__(self):
        """Ensure cleanup on garbage collection."""
        try:
            if hasattr(self, "_loop") and self._loop is not None:
                self._stop_event_loop()
        except Exception:
            # Ignore errors during cleanup in __del__
            pass

    def close(self):
        """Explicit cleanup method for proper resource management."""
        self._stop_event_loop()
